"""Regression coverage for the Bradbury SDK surfaces absent from the stub."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "test" / "stub", ROOT / "test", ROOT / "contracts"):
    sys.path.insert(0, str(folder))

import genlayer
from genlayer import gl
from model import REFERENCE_RULE, ScriptedModel
import retainer as rt


class SDKCompatibilityTests(unittest.TestCase):
    def test_open_brief_without_address_zero_constant(self):
        self.assertFalse(hasattr(genlayer.Address, "ZERO"),
                         "The stub must match Bradbury: Address has no ZERO constant")
        requester = genlayer.Address("0x" + "11" * 20)
        contract = rt.Retainer()
        with patch.object(gl.message, "sender_address", requester), \
                patch.object(gl.message, "value", 100_000), \
                patch.object(gl.nondet, "handler", ScriptedModel(gate="DECIDABLE")):
            brief_id = contract.open_brief(
                "SDK compatibility", REFERENCE_RULE, "0" * 64,
                '["#GenLayer https://example.org", "No tag or link"]', 25_000, 3)
        brief = contract.get_brief(brief_id)
        self.assertEqual(brief["status"], "OPEN")
        self.assertEqual(brief["agent"], "0x" + "00" * 20)
        self.assertEqual(int(contract.escrowed), 100_000)

    def test_withdraw_uses_existing_address_for_evm_recipient(self):
        sender = genlayer.Address("0x" + "22" * 20)
        contract = rt.Retainer()
        amount = 125_000
        contract._credit(sender, amount)
        transfers = []

        def contract_interface(interface):
            self.assertTrue(hasattr(interface, "View"))
            self.assertTrue(hasattr(interface, "Write"))

            def recipient(address):
                self.assertIs(address, sender)

                def emit_transfer(*, value):
                    transfers.append((address, value))

                return SimpleNamespace(emit_transfer=emit_transfer)

            return recipient

        def strict_address(value):
            if isinstance(value, genlayer.Address):
                raise TypeError("cannot convert Address object to bytes")
            return genlayer.Address(value)

        evm = SimpleNamespace(contract_interface=contract_interface)
        with patch.object(gl.message, "sender_address", sender), \
                patch.object(gl, "evm", evm, create=True), \
                patch.object(rt, "Address", strict_address), \
                patch.object(gl.advanced, "emit_transfer",
                             side_effect=AssertionError("stub fallback must not run")):
            self.assertEqual(contract.withdraw(), amount)
            self.assertEqual(contract._balance(sender), 0)
            self.assertEqual(int(contract.credited), 0)
            self.assertEqual(transfers, [(sender, amount)])
            with self.assertRaisesRegex(gl.vm.UserError, "nothing to withdraw"):
                contract.withdraw()
            self.assertEqual(len(transfers), 1)


if __name__ == "__main__":
    unittest.main()
