#!/usr/bin/env python3
"""Build, validate and hash retainer/1 evidence envelopes.

retainer/1 is a profile of suborn/1: identical canonicalization, identical
two-normalization rule, with the attack-specific fields dropped. An honest
deliverable does not declare an attack class.

`normalize_for_dedup` here is a deliberate duplicate of the one in
contracts/retainer.py, which is itself copied byte for byte from
suborn @ 9c7b0af. If the two ever drift, dedup silently breaks, so
test/run_tests.py checks both against the same vectors.

    python3 cli/envelope.py new --brief 0 --body-file work.md --out env.json
    python3 cli/envelope.py check examples/*.json
    python3 cli/envelope.py hash env.json
"""

import argparse
import hashlib
import json
import sys

VERSION = "retainer/1"
PARENT = "suborn/1"
MAX_BODY = 8192

REQUIRED = ("version", "brief_id", "body")
OPTIONAL = ("fetched_from", "author_note")

ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF}


def normalize_for_dedup(body: str) -> str:
    """Dedup normalization is NOT what gets judged.

    Judging sees the body byte for byte, because zero-width characters and
    exotic spacing are themselves attack surface.
    """
    out = []
    for ch in body:
        if ord(ch) in ZERO_WIDTH:
            continue
        if ch.isspace():
            out.append(" ")
            continue
        out.append(ch.lower())
    flat = "".join(out)
    while "  " in flat:
        flat = flat.replace("  ", " ")
    return flat.strip()


def canonical(env: dict) -> str:
    """drop unknown keys, drop empty optionals, sorted keys, no whitespace,
    UTF-8, no ASCII escaping."""
    clean = {k: env[k] for k in REQUIRED if k in env}
    for k in OPTIONAL:
        if k in env and str(env[k]).strip():
            clean[k] = env[k]
    return json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def envelope_hash(env: dict) -> str:
    return hashlib.sha256(canonical(env).encode("utf-8")).hexdigest()


def dedup_fingerprint(body: str) -> str:
    return hashlib.sha256(normalize_for_dedup(body).encode("utf-8")).hexdigest()


INVISIBLE = {
    0x200B: "ZWSP", 0x200C: "ZWNJ", 0x200D: "ZWJ", 0x2060: "WORD-JOINER",
    0xFEFF: "BOM", 0x202A: "LRE", 0x202B: "RLE", 0x202D: "LRO",
    0x202E: "RLO", 0x2066: "LRI", 0x2067: "RLI", 0x2068: "FSI", 0x2069: "PDI",
    0x00AD: "SOFT-HYPHEN", 0x180E: "MONGOLIAN-VOWEL-SEP",
}


def describe(body: str) -> dict:
    """What is in this body that a reader would not see.

    The contract judges the body verbatim, so invisible characters are judged
    too. That is deliberate — they are attack surface, not noise. This exists so
    that whoever sends an envelope knows what they are sending, because finding
    out from a receipt is expensive.
    """
    found = {}
    for ch in body:
        name = INVISIBLE.get(ord(ch))
        if name:
            found[name] = found.get(name, 0) + 1
    return {
        "bytes": len(body.encode("utf-8")),
        "chars": len(body),
        "lines": body.count("\n") + 1,
        "invisible_chars": found,
        "dedup_fingerprint": dedup_fingerprint(body),
    }


def validate(env: dict) -> list:
    problems = []
    if env.get("version") != VERSION:
        problems.append("version must be exactly %s" % VERSION)
    if not isinstance(env.get("brief_id"), int):
        problems.append("brief_id must be an integer")
    body = env.get("body", "")
    if not isinstance(body, str):
        problems.append("body must be a string")
    else:
        size = len(body.encode("utf-8"))
        if size < 1 or size > MAX_BODY:
            problems.append("body must be 1 to %d bytes, got %d" % (MAX_BODY, size))
    for key in env:
        if key not in REQUIRED and key not in OPTIONAL:
            problems.append("unknown key will be dropped from the hash: %s" % key)
    return problems


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_new(args) -> int:
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as fh:
            body = fh.read()
    else:
        body = sys.stdin.read()
    env = {"version": VERSION, "brief_id": args.brief, "body": body}
    if args.fetched_from:
        env["fetched_from"] = args.fetched_from
    if args.author_note:
        env["author_note"] = args.author_note
    problems = validate(env)
    if problems:
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    text = json.dumps(env, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("%s  %s" % (envelope_hash(env), args.out))
    else:
        sys.stdout.write(text)
    return 0


def cmd_check(args) -> int:
    bad = 0
    for path in args.paths:
        env = _load(path)
        problems = validate(env)
        if problems:
            bad += 1
            print("FAIL " + path)
            for p in problems:
                print("       " + p)
        else:
            print("ok   %s  %s" % (path, envelope_hash(env)[:16]))
    return 1 if bad else 0


def cmd_hash(args) -> int:
    env = _load(args.path)
    print(envelope_hash(env))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    new = sub.add_parser("new", help="build an envelope from a body")
    new.add_argument("--brief", type=int, required=True)
    new.add_argument("--body-file")
    new.add_argument("--fetched-from", default="")
    new.add_argument("--author-note", default="")
    new.add_argument("--out")
    new.set_defaults(fn=cmd_new)

    check = sub.add_parser("check", help="validate envelopes")
    check.add_argument("paths", nargs="+")
    check.set_defaults(fn=cmd_check)

    hsh = sub.add_parser("hash", help="print the canonical hash")
    hsh.add_argument("path")
    hsh.set_defaults(fn=cmd_hash)

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
