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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collect_receipts import gen_amount, exact_wei

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
    missing_receipts = [r for r in records if r.get("receipt_available") is False]
    # Older collected records predate receipt_available and remain readable.
    evidence = [r for r in records if r.get("receipt_available") is not False
                and r.get("tx_status") in TERMINAL]
    by_brief = {}
    active_scenarios = {}
    for r in evidence:
        bid = r.get("brief_id")
        if bid is None:
            continue
        scenario = r.get("scenario")
        if scenario is not None:
            active_scenarios[bid] = scenario
        elif bid in active_scenarios:
            # Agent writes contain brief_id but no scenario. Bind them to the
            # preceding explicit attempt, updating on reuse of a failed ID.
            scenario = active_scenarios[bid]
            r = dict(r, scenario=scenario)
        key = ("scenario", str(scenario)) if scenario is not None else ("brief", str(bid))
        by_brief.setdefault(key, []).append(r)

    scenarios = []
    for key in sorted(by_brief):
        rows = by_brief[key]
        # Failed later calls cannot erase state established by a successful
        # transaction. Keep every receipt below, but summarize the latest row
        # that actually carries brief state.
        final = next((r for r in reversed(rows)
                      if r.get("status") and r.get("status") != "NO_STATE_RECORD"), rows[-1])
        bid = final.get("brief_id")
        defence = [final.get("defence_a", ""), final.get("defence_b", "")]
        rounds_run = (1 if defence[0] in {"HELD", "BROKEN"} else 0)
        if defence[0] == "HELD" and defence[1] in {"HELD", "BROKEN"}:
            rounds_run += 1
        scenario = next((r.get("scenario") for r in reversed(rows) if r.get("scenario") is not None), None)
        forgery_attempted = any(r.get("forgery_attempted") is True for r in rows)
        scenarios.append({
            "scenario": scenario,
            "forgery_attempted": forgery_attempted,
            "defence_rounds_run": rounds_run,
            "forgery_caught": (str(scenario) == "3" and forgery_attempted
                               and final.get("judge_raw") == "PASS"
                               and "BROKEN" in defence
                               and final.get("verdict") == "UNVERIFIABLE"),
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
                 "tx_status": r.get("tx_status", ""),
                 **{k: r.get(k) for k in ("receipt_path", "validators", "leader", "execution_result",
                    "consensus_rounds", "fee_wei", "fee_gen", "chain_total_cost_wei",
                    "chain_total_cost_gen")}}
                for r in rows
            ],
        })

    blocked_scenarios = []
    attempted_scenarios = {str(r.get("scenario")) for r in records}
    for scenario in scenarios:
        if str(scenario["scenario"]) != "1" or scenario["gate"] == "DECIDABLE":
            continue
        failed_opens = [tx for tx in scenario["transactions"]
                        if tx["call"] == "open_brief" and
                        (tx["tx_status"] == "UNDETERMINED" or scenario["status"] == "REJECTED")]
        if not failed_opens:
            continue
        dependency = failed_opens[-1]["tx"]
        reason = ("The reference brief did not reach DECIDABLE; the agent cannot "
                  "accept an absent or rejected brief.")
        scenario["note"] = reason
        for number in (2, 3):
            if str(number) not in attempted_scenarios:
                blocked_scenarios.append({"scenario": number, "status": "BLOCKED",
                                          "reason": reason, "depends_on": dependency})

    stored_briefs = {s["brief_id"] for s in scenarios
                     if s["status"] and s["status"] != "NO_STATE_RECORD"}
    brief_attempts = sum(r.get("call") == "open_brief" for r in evidence)
    terminal = evidence
    undetermined = [r for r in records if r.get("tx_status") == "UNDETERMINED"]
    no_state = [r for r in records if r.get("status") == "NO_STATE_RECORD"]

    opened = sum(1 for s in scenarios if s["gate"] == "DECIDABLE")
    refused = sum(1 for s in scenarios if s["status"] == "REJECTED")
    settled = sum(1 for s in scenarios if s["status"] == "SETTLED")
    verdicts = {}
    for s in scenarios:
        if s["verdict"]:
            verdicts[s["verdict"]] = verdicts.get(s["verdict"], 0) + 1

    measured_fees = [int(r["fee_wei"]) for r in evidence if exact_wei(r.get("fee_wei")) is not None]
    report = {
        "missing_receipts": len(missing_receipts),
        "fee_measured_receipts": len(measured_fees),
        "fee_total_wei": str(sum(measured_fees)) if measured_fees else None,
        "fee_total_gen": gen_amount(sum(measured_fees)) if measured_fees else None,
        "defence_rounds_run": sum(s["defence_rounds_run"] for s in scenarios),
        "forgeries_caught": sum(s["forgery_caught"] for s in scenarios),
        "source": source,
        "contract": contract,
        "transactions": len(records),
        "terminal_receipts": len(terminal),
        "undetermined": len(undetermined),
        "no_state_record": len(no_state),
        "briefs": len(stored_briefs),
        "brief_attempts": brief_attempts,
        "blocked_scenarios": blocked_scenarios,
        "opened": opened,
        "refused_by_gate": refused,
        "settled": settled,
        "verdicts": verdicts,
        "gate_refusal_milli": milli(refused, len(stored_briefs)),
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
            "%d terminal transaction(s) did not produce a usable brief state record. "
            "Those transactions do not establish a brief outcome; previously "
            "recorded successful state is retained." % len(no_state))
    if undetermined:
        report["honesty"].append(
            "%d transaction(s) ended UNDETERMINED. Consensus did not produce "
            "an accepted result; this status alone does not establish the cause." % len(undetermined))
    for scenario in scenarios:
        if scenario.get("note"):
            report["honesty"].append("Scenario 1: " + scenario["note"])
    if report["defence_rounds_run"] == 0:
        report["honesty"].append("Defence rounds run: 0. No live defence round was executed.")
    if "3" not in attempted_scenarios:
        report["honesty"].append("Scenario 3: forged delivery not submitted. The defence against forgery has not been demonstrated.")
    if any(r.get("call") == "withdraw" and r.get("tx_status") == "ACCEPTED"
           and r.get("execution_result") == "FINISHED_WITH_RETURN" for r in evidence):
        report["honesty"].append(
            "Withdrawal execution was accepted, but its external transfer runs only "
            "on finalization. This snapshot does not yet prove receipt of funds.")
    if missing_receipts:
        report["honesty"].append("%d transaction(s) have no receipt and are excluded from measurements." % len(missing_receipts))
    if len(measured_fees) != len(evidence):
        report["honesty"].append("Fee totals cover %d of %d terminal receipts; missing fees are not zero-cost measurements." % (len(measured_fees), len(evidence)))
    forgery = [s for s in scenarios if s["forgery_caught"]]
    if not forgery:
        report["honesty"].append(
            "No confirmed scenario-3 forgery fooled the judge with PASS and was then "
            "rejected by a BROKEN defence. UNVERIFIABLE alone is not proof that "
            "a forgery was caught. The live defence demonstration is inconclusive.")
    for scenario in scenarios:
        if (str(scenario["scenario"]) == "3" and scenario["forgery_attempted"]
                and scenario["judge_raw"] == "FAIL"):
            report["honesty"].append(
                "Scenario 3: the forged delivery received FAIL from the original "
                "judge. The attack did not fool the judge, so protection against "
                "a fooled judge remains unproven.")
    if any(s["defence"] == ["BROKEN", "BROKEN"] for s in scenarios):
        report["honesty"].append("BROKEN/BROKEN records only one executed defence round: the contract skips round two after round one fails.")
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

    if source == "bradbury" and report["terminal_receipts"] == 0:
        print("No terminal receipts. Refusing to publish a live measurement.", file=sys.stderr)
        return 2

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
