"""Offline checks for live sequencing; no keys or network."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import retainer_agent as agent

POLICY = {"min_fee": 1000, "max_stake": 1000, "min_fee_to_stake": 2}
BRIEF = {"status": "OPEN", "gate": "DECIDABLE", "fee": 2000,
         "stake_required": 1000, "spec": "Include #GenLayer and a link"}


class SequencedChain:
    def __init__(self, path, fail=None):
        self.path, self.fail, self.calls = path, fail, []

    def brief_count(self):
        return 2

    def get_brief(self, i):
        return BRIEF if i == 0 else dict(BRIEF, status="REJECTED")

    def accept(self, i, stake):
        self.calls.append("accept")
        return "accept"

    def deliver(self, i, envelope):
        self.calls.append("deliver")
        return "deliver"

    def judge(self, i):
        self.calls.append("judge")
        return "judge"

    def wait_success(self, tx):
        # Every transaction must already be durable when waiting begins.
        record = json.loads(Path(self.path).read_text().splitlines()[-1])
        assert record["tx"] == tx
        self.calls.append("wait " + tx)
        if self.fail == tx:
            raise RuntimeError("unsuccessful transaction")


class AgentChainTests(unittest.TestCase):
    def test_sequencing_and_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, decisions = tmp + "/manifest", tmp + "/decisions.json"
            chain = SequencedChain(manifest)
            taken, skipped = agent.work(chain, POLICY, settle=True,
                manifest_path=manifest, decisions_path=decisions, log=lambda _: None)
            self.assertEqual(chain.calls, ["accept", "wait accept", "deliver",
                                          "wait deliver", "judge", "wait judge"])
            records = json.loads(Path(decisions).read_text())
            self.assertEqual([r["take"] for r in records], [True, False])
            self.assertEqual(len(taken), 1)
            self.assertEqual(len(skipped), 1)

    def test_failure_stops_dependent_writes_and_preserves_decision(self):
        for failure in ("accept", "deliver", "judge"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                chain = SequencedChain(tmp + "/manifest", fail=failure)
                with self.assertRaises(RuntimeError):
                    agent.work(chain, POLICY, settle=True, manifest_path=chain.path,
                               decisions_path=tmp + "/decisions", log=lambda _: None)
                self.assertEqual(chain.calls[-1], "wait " + failure)
                self.assertEqual(len(chain.calls), 2 * (1 + ["accept", "deliver", "judge"].index(failure)))
                self.assertTrue(json.loads(Path(tmp + "/decisions").read_text())[0]["take"])

    def test_receipt_success_requires_execution(self):
        chain = agent.BradburyChain("0xcontract", poll=0)
        for result in ("TIMEOUT", "FINISHED_WITH_ERROR", "", None):
            with self.subTest(result=result), patch.object(chain.cr, "fetch_receipt",
                    return_value={"status": "accepted", "execution_result": result}):
                with self.assertRaises(RuntimeError):
                    chain.wait_success("tx")
        with patch.object(chain.cr, "fetch_receipt", side_effect=[
                {"status": "committing", "execution_result": "TIMEOUT"},
                {"status": "accepted", "execution_result": "FINISHED_WITH_RETURN"}]):
            self.assertEqual(chain.wait_success("tx")["status"], "accepted")
        with patch.object(chain.cr, "fetch_receipt", return_value={"status": "undetermined"}):
            with self.assertRaises(RuntimeError):
                chain.wait_success("tx")

    def test_timeout_is_fail_closed(self):
        chain = agent.BradburyChain("0xcontract", wait_timeout=2, poll=0)
        with patch.object(agent.time, "monotonic", side_effect=[0, 1, 1, 1, 3]), \
                patch.object(chain.cr, "fetch_receipt", return_value={"status": "pending"}):
            with self.assertRaises(TimeoutError):
                chain.wait_success("tx")

    def test_scalar_cli_outputs(self):
        chain = agent.BradburyChain("0xcontract")
        for output in ("Result: 3\n", "Result:\n3\n", "3\n", "Result: 3n\n"):
            with self.subTest(output=output), patch.object(agent.subprocess, "run",
                    return_value=SimpleNamespace(returncode=0, stdout=output, stderr="")):
                self.assertEqual(chain.brief_count(), 3)

    def test_rpc_option_reaches_write(self):
        chain = agent.BradburyChain("0xcontract", endpoint="https://rpc.example")
        with patch.object(agent.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout="Transaction Hash: 0x" + "a" * 64, stderr="")) as run:
            chain.accept(0, 1000)
            cmd = run.call_args.args[0]
            self.assertEqual(cmd[cmd.index("--rpc") + 1], "https://rpc.example")
            self.assertEqual(cmd[cmd.index("--args") + 1:], ["0"])


if __name__ == "__main__":
    unittest.main()
