#!/usr/bin/env python3
"""Rehearse the four demo scenarios offline, end to end.

    python3 scripts/dry_run.py
    python3 scripts/dry_run.py --records /tmp/records.jsonl

This is not a measurement and it never becomes one. It exists so that the exact
sequence about to be run against Bradbury has already been run somewhere, and so
that the record shape the collector will produce is fixed before the first
transaction is sent rather than after.

What the stub cannot do is disagree with itself. Every claim on the published
page has to come from receipts.
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("test/stub", "test", "cli", "contracts"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import genlayer as glmod  # noqa: E402
from genlayer import gl  # noqa: E402
from model import ScriptedModel  # noqa: E402
import envelope as envtool  # noqa: E402
import retainer as rt  # noqa: E402

REQUESTER = glmod.Address("0x" + "11" * 20)
AGENT = glmod.Address("0x" + "22" * 20)

BRIEF = json.load(open(os.path.join(ROOT, "calibration", "reference-brief.json"), encoding="utf-8"))
VAGUE = json.load(open(os.path.join(ROOT, "calibration", "vague-brief.json"), encoding="utf-8"))


def as_(addr, value=0):
    gl.message.sender_address = addr
    gl.message.value = value


def load_example(name):
    return json.load(open(os.path.join(ROOT, "examples", name), encoding="utf-8"))


def open_brief(c, brief, model, gate):
    model.gate = gate
    as_(REQUESTER, brief["fee"])
    return c.open_brief(
        title=brief["title"],
        spec=brief["spec"],
        spec_hash="0" * 64,
        probes_json=json.dumps(brief["probes"]),
        stake_required=brief["stake_required"],
        horizon=brief["horizon"],
    )


def run() -> list:
    model = ScriptedModel()
    gl.nondet.handler = model
    gl.advanced.transfers = []
    c = rt.Retainer()
    records = []

    plan = [
        ("1  honest acceptance", BRIEF, "DECIDABLE", "01-honest-pass.json", False),
        ("2  failure against the spec", BRIEF, "DECIDABLE", "02-spec-fail.json", False),
        ("3  caught forgery", BRIEF, "DECIDABLE", "03-forged-pass.json", True),
        ("4  the brief that never opens", VAGUE, "UNDECIDABLE", None, False),
    ]

    for label, brief, gate, example, fooled in plan:
        model.fooled = False
        bid = open_brief(c, brief, model, gate)
        state = c.get_brief(bid)
        print("\nscenario %s" % label)
        print("  gate            %s" % state["gate"])
        print("  status          %s" % state["status"])

        calls = [("open_brief", bid)]

        if example is not None:
            as_(AGENT, brief["stake_required"])
            c.accept(bid)
            calls.append(("accept", bid))

            env = load_example(example)
            env["brief_id"] = bid
            info = envtool.describe(env["body"])
            as_(AGENT, 0)
            env_hash = c.deliver(bid, json.dumps(env))
            calls.append(("deliver", bid))
            print("  envelope        %s" % env_hash[:16])
            print("  body bytes      %d" % info["bytes"])
            if info["invisible_chars"]:
                print("  invisible       %s" % info["invisible_chars"])

            model.fooled = fooled
            verdict = c.judge(bid)
            calls.append(("judge", bid))
            state = c.get_brief(bid)
            print("  judge answered  %s" % state["judge_raw"])
            print("  defence         %s / %s" % (state["defence_a"], state["defence_b"]))
            print("  verdict         %s" % verdict)
            print("  agent credited  %d" % c.balance_of(AGENT.as_hex))
            print("  requester       %d" % c.balance_of(REQUESTER.as_hex))
        else:
            print("  no agent can take it, so there is nothing to deliver")

        for call, b in calls:
            st = c.get_brief(b)
            records.append({
                "brief_id": b, "call": call, "spec_hash": st["spec_hash"],
                "gate": st["gate"], "status": st["status"], "verdict": st["verdict"],
                "judge_raw": st["judge_raw"], "defence_a": st["defence_a"],
                "defence_b": st["defence_b"], "envelope_hash": st["envelope_hash"],
                "body": "", "author_note": "", "tx": "0xdryrun",
                "tx_status": "FINALIZED",
            })

    print("\nsolvency %s" % json.dumps(c.solvency()))
    print("overview %s" % json.dumps(c.get_overview()))
    return records


def main() -> int:
    ap = argparse.ArgumentParser(prog="dry_run")
    ap.add_argument("--records", default="", help="write the record shape the collector will produce")
    args = ap.parse_args()

    records = run()

    if args.records:
        with open(args.records, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("\n%d records -> %s" % (len(records), args.records))

    print("\nNone of the above is evidence. It is the sequence to run on Bradbury.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
