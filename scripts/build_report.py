#!/usr/bin/env python3
"""Build the published report from collected records.

    python3 scripts/build_report.py --records runs/records.jsonl \\
        --contract $CONTRACT --out web/report.json

    python3 scripts/build_report.py --simulate --out web/report.json

The rule this script exists to enforce, carried over from Suborn: a simulated
snapshot is fine for checking the page and the wiring, and it must never be
published as a measurement. So `--simulate` stamps `source: "simulated"` on the
file and every consumer is expected to refuse it, and the receipt-backed path
refuses to write anything at all when it has no records to write.

All arithmetic is in integer thousandths. There are no floats anywhere in a
report, for the same reason there are none in storage.
"""

import argparse
import json
import os
import re
import sys

TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")

TERMINAL = {"FINALIZED", "ACCEPTED", "UNDETERMINED"}
SETTLED_STATUSES = {"SETTLED", "REJECTED", "EXPIRED", "CANCELLED"}


def milli(part: int, whole: int) -> int:
    """Integer thousandths. 0 when there is nothing to divide."""
    if whole <= 0:
        return 0
    return (part * 1000 + whole // 2) // whole


def load_records(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def summarize(records: list, contract: str, source: str) -> dict:
    by_brief = {}
    for r in records:
        bid = r.get("brief_id")
        if bid is None:
            continue
        by_brief.setdefault(bid, []).append(r)

    scenarios = []
    for bid in sorted(by_brief, key=lambda x: (x is None, x)):
        rows = by_brief[bid]
        final = rows[-1]
        scenarios.append({
            "brief_id": bid,
            "spec_hash": final.get("spec_hash", ""),
            "gate": final.get("gate", ""),
            "status": final.get("status", ""),
            "verdict": final.get("verdict", ""),
            "judge_raw": final.get("judge_raw", ""),
            "defence": [final.get("defence_a", ""), final.get("defence_b", "")],
            "envelope_hash": final.get("envelope_hash", ""),
            "author_note": final.get("author_note", ""),
            "transactions": [
                {"call": r.get("call", ""), "tx": r.get("tx", ""),
                 "tx_status": r.get("tx_status", "")}
                for r in rows
            ],
        })

    terminal = [r for r in records if r.get("tx_status") in TERMINAL]
    undetermined = [r for r in records if r.get("tx_status") == "UNDETERMINED"]
    no_state = [r for r in records if r.get("status") == "NO_STATE_RECORD"]

    opened = sum(1 for s in scenarios if s["gate"] == "DECIDABLE")
    refused = sum(1 for s in scenarios if s["status"] == "REJECTED")
    settled = sum(1 for s in scenarios if s["status"] == "SETTLED")
    verdicts = {}
    for s in scenarios:
        if s["verdict"]:
            verdicts[s["verdict"]] = verdicts.get(s["verdict"], 0) + 1

    report = {
        "source": source,
        "contract": contract,
        "transactions": len(records),
        "terminal_receipts": len(terminal),
        "undetermined": len(undetermined),
        "no_state_record": len(no_state),
        "briefs": len(scenarios),
        "opened": opened,
        "refused_by_gate": refused,
        "settled": settled,
        "verdicts": verdicts,
        "gate_refusal_milli": milli(refused, len(scenarios)),
        "scenarios": scenarios,
        "honesty": [],
    }

    # The honesty block is not decoration. Every one of these is a claim the
    # page would otherwise make by omission.
    if source == "simulated":
        report["honesty"].append(
            "Simulated. Not a measurement, must not be published as one.")
    if source == "dry-run":
        report["honesty"].append(
            "Dry run against the local stub. The transaction hashes are "
            "placeholders. Not a measurement, must not be published as one.")
    if no_state:
        report["honesty"].append(
            "%d transaction(s) were terminal with no state record on chain. "
            "Not counted as either outcome." % len(no_state))
    if undetermined:
        report["honesty"].append(
            "%d transaction(s) ended UNDETERMINED, meaning validators did not "
            "agree. That is a result, not an error." % len(undetermined))
    forgery = [s for s in scenarios if s["verdict"] == "UNVERIFIABLE"]
    if not forgery:
        report["honesty"].append(
            "No delivery reached UNVERIFIABLE in this run, so the defence has "
            "not yet been shown to catch anything live. Inconclusive, not a pass.")
    report["honesty"].append(
        "The gate and the defence run inside the Retainer contract. Jastrow and "
        "Suborn receipts are linked evidence, not cross-contract calls.")
    report["honesty"].append(
        "The judging prompt is copied byte for byte from Suborn 9c7b0af, which "
        "is what the 44-attack corpus measured. The defence framings are "
        "adapted and need their own live numbers.")
    return report


SIMULATED = [
    {"brief_id": 0, "call": "open_brief", "spec_hash": "0" * 64, "gate": "DECIDABLE",
     "status": "SETTLED", "verdict": "PASS", "judge_raw": "PASS",
     "defence_a": "HELD", "defence_b": "HELD", "envelope_hash": "a" * 64,
     "body": "", "author_note": "scenario 1", "tx": "0xsim0", "tx_status": "FINALIZED"},
    {"brief_id": 1, "call": "open_brief", "spec_hash": "0" * 64, "gate": "DECIDABLE",
     "status": "SETTLED", "verdict": "FAIL", "judge_raw": "FAIL",
     "defence_a": "HELD", "defence_b": "HELD", "envelope_hash": "b" * 64,
     "body": "", "author_note": "scenario 2", "tx": "0xsim1", "tx_status": "FINALIZED"},
    {"brief_id": 2, "call": "open_brief", "spec_hash": "0" * 64, "gate": "DECIDABLE",
     "status": "SETTLED", "verdict": "UNVERIFIABLE", "judge_raw": "PASS",
     "defence_a": "BROKEN", "defence_b": "PENDING", "envelope_hash": "c" * 64,
     "body": "", "author_note": "scenario 3", "tx": "0xsim2", "tx_status": "FINALIZED"},
    {"brief_id": 3, "call": "open_brief", "spec_hash": "0" * 64, "gate": "UNDECIDABLE",
     "status": "REJECTED", "verdict": "", "judge_raw": "",
     "defence_a": "PENDING", "defence_b": "PENDING", "envelope_hash": "",
     "body": "", "author_note": "scenario 4", "tx": "0xsim3", "tx_status": "FINALIZED"},
]


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_report")
    ap.add_argument("--records", default="")
    ap.add_argument("--contract", default="")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--allow-fake-tx", action="store_true",
                    help="build a dry-run report from records with placeholder hashes")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.simulate:
        records = SIMULATED
        source = "simulated"
        contract = args.contract or "0xSIMULATED"
    else:
        if not args.records:
            print("error: --records or --simulate", file=sys.stderr)
            return 2
        records = load_records(args.records)
        fake = [r.get("tx", "") for r in records if not TX_HASH.match(str(r.get("tx", "")))]
        if fake and not args.allow_fake_tx:
            print("error: %d record(s) have no real transaction hash (e.g. %s).\n"
                  "A dry run is not a measurement. Pass --allow-fake-tx to build a\n"
                  "clearly-labelled dry-run report, or collect real receipts first."
                  % (len(fake), fake[0] or "<empty>"), file=sys.stderr)
            return 2
        source = "dry-run" if fake else "bradbury"
        contract = args.contract
        if not records:
            print("No records. Refusing to write an empty live report; the "
                  "existing one stays in place.", file=sys.stderr)
            return 2
        if not contract:
            print("error: a live report needs --contract", file=sys.stderr)
            return 2

    report = summarize(records, contract, source)

    if not args.simulate and os.path.exists(args.out):
        try:
            with open(args.out, encoding="utf-8") as fh:
                previous = json.load(fh)
            if previous.get("source") == "bradbury" and source != "bradbury":
                print("Refusing to overwrite a receipt-backed report with a %s "
                      "one." % source, file=sys.stderr)
                return 2
            if previous.get("source") == "bradbury" and report["terminal_receipts"] == 0:
                print("Refusing to overwrite a receipt-backed report with one "
                      "that has no terminal receipts.", file=sys.stderr)
                return 2
        except (OSError, ValueError):
            pass

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print("%s report -> %s" % (source, args.out))
    for line in report["honesty"]:
        print("  note: " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
