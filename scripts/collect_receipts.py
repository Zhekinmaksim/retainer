#!/usr/bin/env python3
"""Turn a run manifest into receipt-backed records.

Ported from suborn/scripts/collect_receipts.py @ 9c7b0af. The chain I/O and the
`genlayer call` output parsing are byte for byte the Suborn versions: that
parser earns its keep on output that is nearly-JSON with bare keys and JS
atoms, and rewriting it from memory is how a run gets lost.

The shape is the one that already works in Jastrow: the submitter writes a
manifest line the moment the CLI prints a transaction hash, and this collector
runs later, once receipts have settled. Nothing is lost if the collector dies,
and nothing is estimated if it cannot reach the chain.

    # during the run
    python3 scripts/gl_cmd.py deliver 0 examples/01-honest-pass.json
    # …record {"tx": "0x…", "call": "deliver", "brief_id": 0} per line

    # afterwards
    python3 scripts/collect_receipts.py runs/bradbury.jsonl \\
        --address $CONTRACT --out runs/records.jsonl
    python3 scripts/build_report.py --records runs/records.jsonl --out web/report.json

Offline, for testing the pipeline without a chain:

    python3 scripts/collect_receipts.py runs/manifest.jsonl \\
        --from-json test/fixtures/receipts.json --out /tmp/records.jsonl
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

TERMINAL = {"FINALIZED", "ACCEPTED", "UNDETERMINED", "SUCCESS", "ERROR", "CANCELED"}
EXPLORER = "https://explorer-bradbury.genlayer.com"

RECORD_FIELDS = (
    "brief_id", "call", "spec_hash", "gate", "status", "verdict", "judge_raw",
    "defence_a", "defence_b", "envelope_hash", "body", "author_note",
    "tx", "tx_status",
)


def fetch_json(url: str, timeout: int) -> dict:
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_receipt(explorer: str, tx: str, timeout: int):
    return fetch_json(explorer.rstrip("/") + "/api/v1/transactions/" + tx, timeout)


def replace_js_atoms(source: str) -> str:
    out = []
    index = 0
    quote_char = ""
    escaped = False
    while index < len(source):
        char = source[index]
        if quote_char:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote_char:
                quote_char = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote_char = char
            out.append(char)
            index += 1
            continue
        replaced = False
        for word, value in (("true", "True"), ("false", "False"), ("null", "None")):
            end = index + len(word)
            before = source[index - 1] if index else ""
            after = source[end] if end < len(source) else ""
            if (
                source.startswith(word, index)
                and not (before.isalnum() or before == "_")
                and not (after.isalnum() or after == "_")
            ):
                out.append(value)
                index = end
                replaced = True
                break
        if not replaced:
            out.append(char)
            index += 1
    return "".join(out)


def extract_json(text: str):
    markers = list(re.finditer(r"(?m)^Result:\s*$", text))
    if not markers:
        stripped = text.strip()
        return json.loads(stripped) if stripped.startswith(("{", "[")) else None
    payload = text[markers[-1].end() :]
    payload = re.split(r"\n\s*[✔✖]", payload, maxsplit=1)[0].strip()
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        pass
    quoted = re.sub(r"([,{]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', payload)
    try:
        return ast.literal_eval(replace_js_atoms(quoted))
    except (SyntaxError, ValueError) as exc:
        raise RuntimeError("could not parse genlayer call output: " + str(exc)) from exc


def read_brief(endpoint: str, address: str, brief_id: int, timeout: int):
    command = ["genlayer", "call", address, "get_brief", "--args", str(brief_id)]
    if endpoint:
        command += ["--rpc", endpoint]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        message = (result.stdout + result.stderr).strip()
        normalized = re.sub(r"\s+", " ", message).lower()
        if "unknown brief" in normalized or (
            "missing or invalid parameters" in normalized and "brief" in normalized
        ):
            return None
        raise RuntimeError(message)
    return extract_json(result.stdout)


# diagnose_missing.py imports this name. Kept as an alias so the two scripts
# cannot drift apart silently.
read_submission = read_brief


def status_of(receipt) -> str:
    if not receipt:
        return "PENDING"
    for key in ("status", "status_name", "statusName", "consensus_status"):
        v = receipt.get(key) if isinstance(receipt, dict) else None
        if v:
            return str(v).upper()
    return "PENDING"


def load_manifest(path: str) -> list:
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "tx" not in row:
            raise SystemExit("manifest line has no tx: %s" % line[:80])
        rows.append(row)
    return rows


def load_existing_records(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    records = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        tx = row.get("tx")
        if not tx:
            continue
        missing = [field for field in RECORD_FIELDS if field not in row]
        if missing:
            raise SystemExit("existing record for %s is missing %s" % (tx[:12], ", ".join(missing)))
        records[tx] = row
    return records


def envelope_body(envelope_hash: str, folder: str) -> tuple:
    """Bodies are not on the receipt, they are in the envelopes that were sent.
    Match by hash so a record can never be paired with the wrong document."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli"))
    import envelope as envtool

    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        env = json.load(open(os.path.join(folder, name), encoding="utf-8"))
        if envtool.envelope_hash(env) == envelope_hash:
            return env["body"], env.get("author_note", "")
    return "", ""


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(prog="collect_receipts")
    ap.add_argument("manifest")
    ap.add_argument("--address", default="")
    ap.add_argument("--endpoint", default="", help="optional RPC URL passed to genlayer call")
    ap.add_argument("--explorer", default=EXPLORER)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--from-json", default="", help="cached receipts, for offline runs")
    ap.add_argument("--examples", default=os.path.join(root, "examples"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--wait", type=int, default=0, help="seconds to keep polling non-terminal transactions")
    args = ap.parse_args()

    rows = load_manifest(args.manifest)
    cache = json.load(open(args.from_json, encoding="utf-8")) if args.from_json else None

    # One read per brief, not per transaction: a brief is touched by open,
    # accept, deliver and judge, and its final state is the same for all four.
    briefs = {}
    if cache is None and args.address:
        for row in rows:
            bid = row.get("brief_id")
            if bid is None or bid in briefs:
                continue
            briefs[bid] = read_brief(args.endpoint, args.address, int(bid), args.timeout)

    records, pending, missing = [], [], []
    for row in rows:
        tx = row["tx"]
        bid = row.get("brief_id")

        if cache is not None:
            entry = cache.get(tx) or {}
            receipt = entry.get("receipt")
            state = entry.get("brief")
        else:
            deadline = time.time() + args.wait
            while True:
                receipt = fetch_receipt(args.explorer, tx, args.timeout)
                if status_of(receipt) in TERMINAL or time.time() > deadline:
                    break
                time.sleep(4)
            state = briefs.get(bid)

        st = status_of(receipt)
        if st not in TERMINAL:
            pending.append(tx)
            continue

        state = state or {}
        if not state:
            # Terminal on the explorer but no state on chain. This is the exact
            # failure that ate six Suborn transactions. It is recorded as its
            # own outcome, never silently dropped.
            missing.append(tx)

        env_hash = state.get("envelope_hash") or row.get("envelope_hash", "")
        body, note = envelope_body(env_hash, args.examples) if env_hash else ("", "")

        records.append({
            "brief_id": bid,
            "call": row.get("call", ""),
            "spec_hash": state.get("spec_hash", row.get("spec_hash", "")),
            "gate": state.get("gate", ""),
            "status": state.get("status", "" if state else "NO_STATE_RECORD"),
            "verdict": state.get("verdict", ""),
            "judge_raw": state.get("judge_raw", ""),
            "defence_a": state.get("defence_a", ""),
            "defence_b": state.get("defence_b", ""),
            "envelope_hash": env_hash,
            "body": body,
            "author_note": note,
            "tx": tx,
            "tx_status": st,
        })

    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({k: r[k] for k in RECORD_FIELDS}, ensure_ascii=False) + "\n")

    print("%d records -> %s" % (len(records), args.out))
    if pending:
        print("%d still settling, re-run later: %s"
              % (len(pending), ", ".join(t[:12] for t in pending[:5])))
    if missing:
        print("%d terminal with no state record: %s"
              % (len(missing), ", ".join(t[:12] for t in missing[:5])))
        print("Run scripts/diagnose_missing.py before publishing anything about these.")
    if not records:
        print("Nothing collected. Do not build a report from this — leave the old one in place.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
