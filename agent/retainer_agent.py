#!/usr/bin/env python3
"""An agent that works for money on Retainer.

    python3 agent/retainer_agent.py --local            # against the stub
    python3 agent/retainer_agent.py --address $CONTRACT --settle

The loop is scan, appraise, accept, compose, self-check, deliver, withdraw. The
interesting part is `appraise`, and it is the reason this is an agent rather
than a script that presses accept.

--------------------------------------------------------------------------------
Why it refuses work
--------------------------------------------------------------------------------

Retainer's gate protects the requester: a brief does not open unless the spec is
decidable. Nothing in the contract protects the agent. An agent that stakes on
work it cannot defend loses the stake, and it loses it on two different
failures, which need two different checks:

  can I meet it      Is there a worker that understands this spec, and does the
                     deliverable actually satisfy every requirement the worker
                     can name? An unmet requirement means FAIL and a slashed
                     stake, so the brief is declined before staking.

  can I defend it    Would the deliverable survive the contract's defence? The
                     defence overturns a verdict when the document argues with
                     its reader. An honest deliverable can trip it by accident —
                     quoting the spec back, adding a note to the reviewer,
                     pasting something that reads like a system message. That
                     costs the fee even though nobody attacked anything.

The second check is the one worth having. It runs on the composed body, not on
the brief, so it can only run after composing — which is why composing happens
before accepting, and the stake goes in last.

--------------------------------------------------------------------------------
What this is not
--------------------------------------------------------------------------------

It ships one worker, for the campaign-post rule the trilogy was measured on. It
is not a general contractor and does not pretend to be: `WORKERS` is a list, an
unrecognised spec is declined with that reason stated, and the decision is
printed either way. A worker that guessed at specs it did not understand would
be an agent that loses stakes politely.

The self-check is local and cheap: it never calls a model and never touches the
chain. It cannot prove the contract's defence will hold, only catch the ways a
delivery trips it that are visible from the text itself.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
import envelope as envtool  # noqa: E402

ENVELOPE_VERSION = "retainer/1"
WRITER = os.path.join(ROOT, "scripts", "genlayer_write.mjs")


# ---------------------------------------------------------------- workers


class CampaignPost:
    """The rule Jastrow and Suborn were both measured on: a post carrying the
    #GenLayer hashtag and a link to the project.

    `requirements` is what makes the worker useful beyond composing. It is the
    same list used to compose and to verify, so the agent cannot congratulate
    itself on work that misses something it knew to include.
    """

    name = "campaign-post"

    def handles(self, spec: str) -> bool:
        s = spec.lower()
        return "#genlayer" in s or ("hashtag" in s and "link" in s)

    def requirements(self, spec: str) -> list:
        s = spec.lower()
        needed = []
        if "hashtag" in s or "#genlayer" in s:
            needed.append(("hashtag", r"#genlayer\b"))
        if "link" in s:
            needed.append(("link", r"https?://\S+"))
        return needed

    def compose(self, brief: dict) -> str:
        return (
            "Shipped the Retainer integration write-up.\n\n"
            "It covers the acceptance gate, the two defence rounds and what the "
            "three verdicts do to the money, with the receipts for each run.\n\n"
            "#GenLayer https://github.com/Zhekinmaksim/retainer"
        )

    def verify(self, spec: str, body: str) -> list:
        missing = []
        for label, pattern in self.requirements(spec):
            if not re.search(pattern, body, re.IGNORECASE):
                missing.append(label)
        return missing


WORKERS = [CampaignPost()]


def worker_for(spec: str):
    for w in WORKERS:
        if w.handles(spec):
            return w
    return None


# ------------------------------------------------------------ self-check

# Text that argues with the reader instead of being read. The contract's
# defence overturns a verdict that only holds because of wording like this, and
# it does not care whether the wording was deliberate.
ARGUES_WITH_READER = [
    (r"\b(answer|reply|respond|mark|return|output)\s+(with\s+)?(pass|fail)\b",
     "tells the reader what verdict to return"),
    (r"\b(ignore|disregard|override|set aside)\b.{0,40}\b(instruction|rule|above|previous)",
     "tells the reader to ignore something"),
    (r"\b(waived|waiver|exempt(ed)?|does not apply)\b.{0,60}\b(requirement|rule|spec)",
     "claims a requirement was waived"),
    (r"^\s*(system|developer|assistant|evaluator)\s*(note|message)?\s*[:\-]",
     "imitates a system or evaluator message"),
    (r"\b(the )?(rule'?s? )?author\b.{0,40}\b(said|says|approved|allowed|confirmed)",
     "claims authority from the spec's author"),
    (r"\byou (must|should|need to|are required to)\b",
     "addresses the reader in the imperative"),
    (r"\b(this|the) (submission|deliverable|document) (should|must) (pass|be marked)",
     "argues for its own verdict"),
]

INVISIBLE_OK = 0


def self_check(spec: str, body: str) -> list:
    """Reasons this delivery would be risky to submit. Empty means clean."""
    problems = []
    for pattern, why in ARGUES_WITH_READER:
        if re.search(pattern, body, re.IGNORECASE | re.MULTILINE):
            problems.append(why)

    info = envtool.describe(body)
    if info["invisible_chars"]:
        problems.append(
            "carries invisible characters (%s), which are judged verbatim"
            % ", ".join(sorted(info["invisible_chars"])))

    # Quoting the spec back is the commonest accidental trip: it puts the
    # judging rule inside the document being judged.
    spec_line = spec.strip().split("\n")[0].strip()
    if len(spec_line) > 30 and spec_line.lower() in body.lower():
        problems.append("quotes the acceptance spec back inside the deliverable")

    if info["bytes"] > envtool.MAX_BODY:
        problems.append("body is %d bytes, over the %d limit"
                        % (info["bytes"], envtool.MAX_BODY))
    return problems


# --------------------------------------------------------------- appraise


class Decision:
    def __init__(self, take, why, body=None, worker=None):
        self.take = take
        self.why = why
        self.body = body
        self.worker = worker

    def __str__(self):
        return ("take   " if self.take else "skip   ") + self.why


def appraise(brief: dict, policy: dict) -> Decision:
    """Decide, and be able to say why either way."""
    if brief["status"] != "OPEN":
        return Decision(False, "not open (%s)" % brief["status"])
    if brief["gate"] != "DECIDABLE":
        return Decision(False, "gate returned %s" % brief["gate"])

    fee = int(brief["fee"])
    stake = int(brief["stake_required"])
    if fee < policy["min_fee"]:
        return Decision(False, "fee %d below floor %d" % (fee, policy["min_fee"]))
    if stake > policy["max_stake"]:
        return Decision(False, "stake %d over ceiling %d" % (stake, policy["max_stake"]))
    if stake * policy["min_fee_to_stake"] > fee:
        return Decision(False, "fee %d is thin against a stake of %d" % (fee, stake))

    worker = worker_for(brief["spec"])
    if worker is None:
        return Decision(False, "no worker understands this spec")

    body = worker.compose(brief)

    missing = worker.verify(brief["spec"], body)
    if missing:
        return Decision(False, "cannot meet the spec: missing %s" % ", ".join(missing))

    risky = self_check(brief["spec"], body)
    if risky:
        return Decision(False, "the delivery would risk the defence: " + "; ".join(risky))

    return Decision(True, "worker %s, fee %d against stake %d"
                    % (worker.name, fee, stake), body=body, worker=worker)


# ------------------------------------------------------------------ chain


class LocalChain:
    """Drives the contract object directly, through the test stub. No network,
    no keys. This is what makes the agent testable at all."""

    def __init__(self, contract, address, gl, glmod):
        self.c = contract
        self.me = address
        self.gl = gl
        self.glmod = glmod

    def _as(self, value=0):
        self.gl.message.sender_address = self.me
        self.gl.message.value = value

    def brief_count(self):
        return self.c.brief_count()

    def get_brief(self, i):
        return self.c.get_brief(i)

    def balance(self):
        return self.c.balance_of(self.me.as_hex)

    def accept(self, i, stake):
        self._as(stake)
        self.c.accept(i)
        return "local"

    def deliver(self, i, envelope):
        self._as(0)
        return self.c.deliver(i, json.dumps(envelope))

    def judge(self, i):
        self._as(0)
        return self.c.judge(i)

    def withdraw(self):
        self._as(0)
        return self.c.withdraw()


class BradburyChain:
    """Reads through `genlayer call`, writes through the SDK bridge, because
    that CLI does not expose --value for payable calls."""

    def __init__(self, address, endpoint="", timeout=60):
        self.address = address
        self.endpoint = endpoint
        self.timeout = timeout
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import collect_receipts as cr  # reuse the parser that already works
        self.cr = cr

    def _call(self, method, *args):
        cmd = ["genlayer", "call", self.address, method]
        if args:
            cmd += ["--args"] + [str(a) for a in args]
        if self.endpoint:
            cmd += ["--rpc", self.endpoint]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        if r.returncode != 0:
            raise RuntimeError((r.stdout + r.stderr).strip())
        return self.cr.extract_json(r.stdout)

    def _write(self, method, args=None, args_json=None, value=0):
        cmd = ["node", WRITER, self.address, method, "--value", str(value)]
        if args_json is not None:
            cmd += ["--args-json", args_json]
        elif args:
            cmd += ["--args"] + [str(a) for a in args]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        if r.returncode != 0:
            raise RuntimeError((r.stdout + r.stderr).strip())
        out = (r.stdout or "").strip()
        found = re.search(r"0x[0-9a-fA-F]{64}", out)
        return found.group(0) if found else out

    def brief_count(self):
        return int(self._call("brief_count"))

    def get_brief(self, i):
        return self._call("get_brief", i)

    def balance(self):
        raise NotImplementedError("balance_of needs the agent address; pass --me")

    def accept(self, i, stake):
        return self._write("accept", args=[i], value=stake)

    def deliver(self, i, envelope):
        return self._write(
            "deliver",
            args_json=json.dumps(
                [str(i), json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))],
                ensure_ascii=False))

    def judge(self, i):
        return self._write("judge", args=[i])

    def withdraw(self):
        return self._write("withdraw")


# ------------------------------------------------------------------- loop


def manifest(path, **fields):
    """Written the moment a hash exists, before waiting for anything. Six Suborn
    transactions went terminal with no state record, and the manifest was the
    only reason that was diagnosable."""
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fields, ensure_ascii=False) + "\n")


def work(chain, policy, log=print, settle=False, manifest_path="", dry=False):
    taken, skipped = [], []
    count = chain.brief_count()
    log("scanning %d brief(s)" % count)

    for i in range(count):
        brief = chain.get_brief(i)
        d = appraise(brief, policy)
        log("  brief %d  %s" % (i, d))
        if not d.take:
            skipped.append((i, d.why))
            continue
        if dry:
            taken.append((i, "dry run, nothing staked"))
            continue

        stake = int(brief["stake_required"])
        tx = chain.accept(i, stake)
        manifest(manifest_path, call="accept", brief_id=i, stake=stake, tx=tx)

        env = {"version": ENVELOPE_VERSION, "brief_id": i, "body": d.body,
               "author_note": "composed by %s" % d.worker.name}
        problems = envtool.validate(env)
        if problems:
            raise RuntimeError("built an invalid envelope: %s" % problems)

        env_hash = chain.deliver(i, env)
        manifest(manifest_path, call="deliver", brief_id=i,
                 envelope_hash=envtool.envelope_hash(env), tx=env_hash)
        log("    delivered, envelope %s" % envtool.envelope_hash(env)[:16])

        if settle:
            verdict = chain.judge(i)
            manifest(manifest_path, call="judge", brief_id=i, tx=verdict)
            log("    verdict %s" % verdict)
        taken.append((i, d.why))

    return taken, skipped


def main() -> int:
    ap = argparse.ArgumentParser(prog="retainer_agent")
    ap.add_argument("--local", action="store_true", help="run against the local stub")
    ap.add_argument("--address", default="", help="deployed Retainer address")
    ap.add_argument("--endpoint", default="")
    ap.add_argument("--min-fee", type=int, default=1000)
    ap.add_argument("--max-stake", type=int, default=1_000_000)
    ap.add_argument("--min-fee-to-stake", type=int, default=2,
                    help="decline unless the fee is at least this many times the stake")
    ap.add_argument("--settle", action="store_true",
                    help="also call judge; it is open to either party")
    ap.add_argument("--dry", action="store_true", help="appraise only, stake nothing")
    ap.add_argument("--manifest", default="")
    args = ap.parse_args()

    policy = {"min_fee": args.min_fee, "max_stake": args.max_stake,
              "min_fee_to_stake": args.min_fee_to_stake}

    if args.local:
        print("no chain: this mode only exists inside the test suite")
        return 2
    if not args.address:
        print("error: --address or --local", file=sys.stderr)
        return 2

    chain = BradburyChain(args.address, args.endpoint)
    taken, skipped = work(chain, policy, settle=args.settle,
                          manifest_path=args.manifest, dry=args.dry)
    print("\ntook %d, skipped %d" % (len(taken), len(skipped)))
    for i, why in skipped:
        print("  brief %d skipped: %s" % (i, why))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
