#!/usr/bin/env python3
"""Print the exact `genlayer` CLI invocations, with arguments escaped.

Nothing here talks to a chain. It exists because the arguments are long JSON
blobs with embedded newlines and invisible characters, and hand-quoting them in
a shell is how a delivery gets silently corrupted before it is ever judged.

    export CONTRACT=0x...
    python3 scripts/gl_cmd.py open    calibration/reference-brief.json
    python3 scripts/gl_cmd.py accept  0 --stake 25000
    python3 scripts/gl_cmd.py deliver 0 examples/01-honest-pass.json
    python3 scripts/gl_cmd.py judge   0
    python3 scripts/gl_cmd.py withdraw

Every write prints a manifest line as well. Record it the moment the CLI prints
a transaction hash, before waiting for any receipt. In the Suborn run six
transactions never produced a state record, and the only reason that was
diagnosable at all was the manifest.
"""

import argparse
import hashlib
import json
import os
import shlex
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
import envelope as envtool  # noqa: E402

WRITER = "node scripts/genlayer_write.mjs"


def q(value) -> str:
    if isinstance(value, str):
        return shlex.quote(value)
    return shlex.quote(json.dumps(value))


def manifest_hint(**fields) -> None:
    print("# manifest line, append to runs/bradbury.jsonl with the printed hash:")
    print("#   " + json.dumps(dict(fields, tx="0x…"), ensure_ascii=False))


def cmd_open(args) -> int:
    brief = json.load(open(args.path, encoding="utf-8"))
    spec = brief["spec"]
    spec_hash = hashlib.sha256(spec.encode("utf-8")).hexdigest()
    probes = json.dumps(brief["probes"], ensure_ascii=False, separators=(",", ":"))
    encoded = json.dumps(
        [
            brief["title"],
            spec,
            spec_hash,
            probes,
            str(brief["stake_required"]),
            str(brief["horizon"]),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    print("# spec_hash %s" % spec_hash)
    print("# the gate runs inside this call. Three outcomes are all publishable:")
    print("#   DECIDABLE          brief opens, fee escrowed")
    print("#   AMBIGUOUS/UNDEC.   brief stored REJECTED, fee returned")
    print("#   validators split   transaction ends UNDETERMINED")
    print(
        " \\\n  ".join(
            [WRITER, args.address or "$CONTRACT", "open_brief",
             "--value", str(brief["fee"]), "--args-json", q(encoded)]
        )
    )
    manifest_hint(call="open_brief", spec_hash=spec_hash, fee=brief["fee"])
    return 0


def cmd_accept(args) -> int:
    print(
        " \\\n  ".join(
            [WRITER, args.address or "$CONTRACT", "accept",
             "--value", str(args.stake), "--args", str(args.brief)]
        )
    )
    manifest_hint(call="accept", brief_id=args.brief, stake=args.stake)
    return 0


def cmd_deliver(args) -> int:
    env = json.load(open(args.path, encoding="utf-8"))
    env["brief_id"] = args.brief
    problems = envtool.validate(env)
    if problems:
        for p in problems:
            print("error: %s" % p, file=sys.stderr)
        return 2
    payload = json.dumps(env, ensure_ascii=False, separators=(",", ":"))
    info = envtool.describe(env["body"])
    env_hash = envtool.envelope_hash(env)
    print("# envelope_hash %s" % env_hash)
    print("# dedup_key     %s" % info["dedup_fingerprint"])
    print("# body bytes    %d" % info["bytes"])
    if info["invisible_chars"]:
        print("# invisible     %s" % info["invisible_chars"])
        print("# these are judged verbatim. If they are not deliberate, remove them now.")
    print(
        " \\\n  ".join(
            [WRITER, args.address or "$CONTRACT", "deliver",
             "--args", str(args.brief), q(payload)]
        )
    )
    manifest_hint(call="deliver", brief_id=args.brief, envelope_hash=env_hash)
    return 0


def cmd_judge(args) -> int:
    print("# this is the expensive nondeterministic call: gate-free, but it runs")
    print("# the judge and up to two defence rounds. It can end UNDETERMINED;")
    print("# nothing has to be unwound if it does, just call it again.")
    print("%s %s judge --args %d" % (WRITER, args.address or "$CONTRACT", args.brief))
    manifest_hint(call="judge", brief_id=args.brief)
    return 0


def cmd_simple(args) -> int:
    parts = [WRITER, args.address or "$CONTRACT", args.cmd]
    if args.cmd in ("cancel_brief", "expire"):
        parts += ["--args", str(args.brief)]
    print(" ".join(parts))
    manifest_hint(call=args.cmd, brief_id=getattr(args, "brief", None))
    return 0


def cmd_read(args) -> int:
    """Reads are free and go through the plain CLI, not the value bridge."""
    for call, extra in (
        ("get_overview", ""),
        ("solvency", ""),
        ("get_brief", " --args %d" % args.brief),
        ("get_delivery", " --args %d" % args.brief),
    ):
        print("genlayer call %s %s%s" % (args.address or "$CONTRACT", call, extra))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="gl_cmd")
    ap.add_argument("--address", default="")
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("open")
    o.add_argument("path")
    o.add_argument("--address", default="")
    o.set_defaults(fn=cmd_open)

    a = sub.add_parser("accept")
    a.add_argument("brief", type=int)
    a.add_argument("--stake", type=int, required=True)
    a.add_argument("--address", default="")
    a.set_defaults(fn=cmd_accept)

    d = sub.add_parser("deliver")
    d.add_argument("brief", type=int)
    d.add_argument("path")
    d.add_argument("--address", default="")
    d.set_defaults(fn=cmd_deliver)

    j = sub.add_parser("judge")
    j.add_argument("brief", type=int)
    j.add_argument("--address", default="")
    j.set_defaults(fn=cmd_judge)

    for name in ("cancel_brief", "expire"):
        p = sub.add_parser(name)
        p.add_argument("brief", type=int)
        p.add_argument("--address", default="")
        p.set_defaults(fn=cmd_simple)

    w = sub.add_parser("withdraw")
    w.add_argument("--address", default="")
    w.set_defaults(fn=cmd_simple)

    r = sub.add_parser("read")
    r.add_argument("brief", type=int, nargs="?", default=0)
    r.add_argument("--address", default="")
    r.set_defaults(fn=cmd_read)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
