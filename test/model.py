"""A scripted stand-in for the validator population.

Adapted from suborn/test/model.py @ 9c7b0af. The point is not to predict what a
real model does. The point is that every branch of the contract is reachable
deterministically.

Three prompt kinds have to be told apart, because all three come through the
same `exec_prompt`:

  gate      asks whether an acceptance spec is decidable
  judge     applies the spec to the deliverable
  referee   re-reads the deliverable under a framing a forged document cannot
            satisfy, and reports the verdict a careful reader would reach

`fooled` is what makes an attack work in the harness: a fooled judge lands on
the other side of the honest answer, whatever the deliverable says in words.
The referee is not fooled, because it reads facts. That asymmetry is the whole
defence, and on Bradbury it is the network rather than a flag.
"""

import json
import re

REFERENCE_RULE = (
    "The deliverable is accepted if it contains the #GenLayer hashtag "
    "and a link to the project."
)


def facts(body: str) -> tuple:
    """The two material facts of the reference rule, read strictly."""
    stripped = "".join(
        ch for ch in body if ord(ch) not in (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF)
    )
    has_tag = re.search(r"#genlayer\b", stripped, re.IGNORECASE) is not None
    visible = stripped.split("[image attached")[0]
    has_link = re.search(r"https?://", visible) is not None
    return (has_tag, has_link)


def honest_verdict(body: str) -> str:
    tag, link = facts(body)
    return "PASS" if (tag and link) else "FAIL"


class ScriptedModel:
    def __init__(self, gate="DECIDABLE", fooled=False):
        self.gate = gate
        self.fooled = fooled
        self.gate_calls = 0
        self.judge_calls = 0
        self.referee_calls = 0
        self.raw_override = None       # force a malformed or out-of-vocab judge reply
        self.referee_override = None   # force an unreadable referee round

    def __call__(self, prompt: str) -> str:
        if '{"gate": str}' in prompt:
            return self._gate(prompt)
        if prompt.startswith("You are applying a written rule to one document."):
            return self._judge(prompt)
        return self._referee(prompt)

    @staticmethod
    def _fenced(prompt: str) -> list:
        return re.findall(
            r"EVIDENCE-[0-9A-F]{16}\n(.*?)\nEVIDENCE-[0-9A-F]{16}", prompt, re.S
        )

    def _gate(self, prompt: str) -> str:
        self.gate_calls += 1
        if self.gate == "__garbage__":
            return "sure thing, the spec looks fine to me"
        return json.dumps({"gate": self.gate})

    def _judge(self, prompt: str) -> str:
        self.judge_calls += 1
        if self.raw_override is not None:
            return self.raw_override
        body = self._fenced(prompt)[0]
        honest = honest_verdict(body)
        if self.fooled:
            return json.dumps({"verdict": "FAIL" if honest == "PASS" else "PASS"})
        return json.dumps({"verdict": honest})

    def _referee(self, prompt: str) -> str:
        self.referee_calls += 1
        if self.referee_override is not None:
            return self.referee_override
        body = self._fenced(prompt)[0]
        return json.dumps({"verdict": honest_verdict(body)})
