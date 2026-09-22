#!/usr/bin/env python3
"""Find out why a terminal transaction produced no brief state.

Ported from suborn/scripts/diagnose_missing.py @ 9c7b0af, unchanged except for
the artefact names. It borrows its chain I/O from collect_receipts.py rather
than describing those calls a second time.

Version 2. The first version spoke JSON-RPC and got UNKNOWN for everything,
because that is not how this repo talks to Bradbury: receipts come from the
explorer over HTTP, contract state comes from the `genlayer call` CLI. Rather than
describe those calls a second time and get them wrong a second time, this
imports them from scripts/collect_receipts.py. If the collector can read the
chain, so can this. If it cannot, both fail the same way.

    python3 scripts/diagnose_missing.py \
        --address $CONTRACT \
        --manifest runs/bradbury.jsonl \
        --scan 60 \
        --out runs/diagnosis.json

Three questions per transaction:

  1. what does the explorer receipt say
  2. is the brief on chain under an id other than the one recorded
  3. if it is nowhere, did the transaction actually fail

Question 2 is the one worth the scan. If a brief turns up under a different
id, nothing was lost and the report is short of records that exist.

--scan reads ids one at a time through the CLI, so 60 ids is 60 processes and a
couple of minutes. Run it once and keep runs/diagnosis.json.
"""

import argparse
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILED = {"ERROR", "CANCELED", "REVERTED", "FAILED"}
SETTLED = {"FINALIZED", "ACCEPTED", "UNDETERMINED"}


def load_collector():
    """Borrow the working chain I/O instead of reimplementing it."""
    path = os.path.join(ROOT, "scripts", "collect_receipts.py")
    spec = importlib.util.spec_from_file_location("collect_receipts", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("fetch_receipt", "read_submission", "status_of"):
        if not hasattr(mod, name):
            raise SystemExit("collect_receipts.py has no %s - the two scripts have drifted" % name)
    return mod


def dig(obj, *names):
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in names and v not in (None, "", [], {}):
                    found.append((k, v))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return found


def main() -> int:
    c = load_collector()

    ap = argparse.ArgumentParser(prog="diagnose_missing")
    ap.add_argument("--address", required=True)
    ap.add_argument("--manifest", default=os.path.join(ROOT, "runs", "bradbury.jsonl"))
    ap.add_argument("--report", default=os.path.join(ROOT, "web", "report.json"))
    ap.add_argument("--explorer", default=getattr(c, "EXPLORER", "https://explorer-bradbury.genlayer.com"))
    ap.add_argument("--endpoint", default="", help="optional RPC URL passed through to genlayer call")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--scan", type=int, default=0)
    ap.add_argument("--tx", action="append", default=[])
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    on_chain = set()
    if os.path.exists(args.report):
        snap = json.load(open(args.report, encoding="utf-8"))
        on_chain = {r["envelope_hash"] for r in snap.get("records", [])}

    rows = []
    for line in open(args.manifest, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))

    targets = [r for r in rows if r["tx"] in args.tx] if args.tx else \
              [r for r in rows if r.get("envelope_hash") and r["envelope_hash"] not in on_chain]
    print("%d transactions to explain\n" % len(targets))

    index = {}
    if args.scan:
        print("scanning brief ids 0..%d through `genlayer call`" % (args.scan - 1))
        blank = 0
        for i in range(args.scan):
            try:
                got = c.read_submission(args.endpoint, args.address, i, args.timeout)
            except Exception as e:
                print("  id %d: read failed (%s)" % (i, str(e)[:90]))
                blank += 1
                if blank >= 3 and not index:
                    print("")
                    print("  Three reads in a row failed and nothing has been read at all.")
                    print("  That is a client problem, not an empty contract. Check that")
                    print("  `genlayer call %s get_brief --args 0` works by hand" % args.address[:12])
                    print("  before trusting anything below.")
                    print("")
                    break
                continue
            if isinstance(got, dict) and got.get("envelope_hash"):
                blank = 0
                index[got["envelope_hash"]] = {"brief_id": i, "brief": got}
            else:
                blank += 1
        print("  %d briefs readable on chain\n" % len(index))
        if not index:
            print("  Nothing was read. Every verdict below is therefore UNRESOLVED,")
            print("  not evidence that the briefs are absent.\n")

    results = []
    for row in targets:
        tx = row["tx"]
        env_hash = row.get("envelope_hash", "")
        try:
            receipt = c.fetch_receipt(args.explorer, tx, args.timeout)
        except Exception as e:
            receipt = None
            print("%s  explorer lookup failed: %s" % (tx[:14], str(e)[:80]))
        st = c.status_of(receipt)
        errors = dig(receipt, "error", "errorMessage", "message", "revert_reason", "err")

        hit = index.get(env_hash)
        if hit:
            verdict = "RECOVERABLE - on chain as brief %d, the collector read the wrong slot" % hit["brief_id"]
        elif not args.scan or not index:
            verdict = "UNRESOLVED - receipt says %s, and no brief state was read to compare against" % st
        elif st in FAILED:
            verdict = "FAILED ON CHAIN - the transaction did not land, nothing to recover"
        elif st in SETTLED:
            verdict = "SETTLED WITHOUT STATE - accepted by consensus but wrote no submission, so the contract rejected the call"
        else:
            verdict = "UNRESOLVED - receipt status %s" % st

        print("%s  %s" % (tx[:14], row.get("file", env_hash[:12])))
        print("   receipt status : %s" % st)
        if errors:
            print("   fields         : %s" % json.dumps(errors[:2], ensure_ascii=False)[:220])
        print("   -> %s\n" % verdict)

        results.append({
            "tx": tx, "file": row.get("file", ""), "envelope_hash": env_hash,
            "status": st, "verdict": verdict,
            "recovered_as": hit["brief_id"] if hit else None,
            "recovered_record": hit["submission"] if hit else None,
        })

    recoverable = [r for r in results if r["recovered_as"] is not None]
    unresolved = [r for r in results if r["verdict"].startswith("UNRESOLVED")]
    print("=" * 72)
    print("%d recoverable, %d unresolved, %d explained"
          % (len(recoverable), len(unresolved), len(results) - len(recoverable) - len(unresolved)))
    if recoverable:
        print("")
        print("Add these ids to the manifest and re-run make publish:")
        for r in recoverable:
            print("  %s -> submission %d" % (r["file"] or r["envelope_hash"][:12], r["recovered_as"]))
    if unresolved:
        print("")
        print("Unresolved is not an answer. Do not write 'rejected by the contract'")
        print("in the submission on the strength of it - say six transactions have no")
        print("submission state and the cause was not established.")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        json.dump(results, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("")
        print("written: %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
