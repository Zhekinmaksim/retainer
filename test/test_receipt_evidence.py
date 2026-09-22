"""Focused checks for live evidence accounting; run with unittest discovery."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect_receipts import gen_amount, receipt_evidence
from build_report import summarize


class ReceiptEvidenceTests(unittest.TestCase):
    def record(self, **changes):
        return dict(dict(brief_id=2, scenario=3, forgery_attempted=True,
                         tx='0x' + 'a' * 64, tx_status='ACCEPTED',
                         receipt_available=True, status='SETTLED',
                         judge_raw='PASS', verdict='UNVERIFIABLE',
                         defence_a='BROKEN', defence_b='BROKEN'), **changes)

    def report(self, **changes):
        return summarize([self.record(**changes)], '0xcontract', 'bradbury')

    def test_exact_amounts_and_missing_fee(self):
        self.assertEqual(gen_amount('9007199254740993000000000000000001'),
                         '9007199254740993.000000000000000001')
        self.assertEqual(gen_amount(173300700), '0.000000000173300700')
        self.assertIsNone(gen_amount(1.0))
        self.assertIsNone(receipt_evidence({'status': 'accepted'})['fee_wei'])
        report = self.report()
        self.assertEqual(report['fee_measured_receipts'], 0)
        self.assertIsNone(report['fee_total_gen'])

    def test_forgery_requires_all_evidence(self):
        self.assertEqual(self.report()['forgeries_caught'], 1)
        for changes in ({'forgery_attempted': False}, {'scenario': 1},
                        {'judge_raw': 'MALFORMED'}, {'judge_raw': 'FAIL'},
                        {'verdict': 'PASS'}, {'defence_a': 'HELD', 'defence_b': 'HELD'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.report(**changes)['forgeries_caught'], 0)

    def test_short_circuit_defence_rounds(self):
        self.assertEqual(self.report()['defence_rounds_run'], 1)
        self.assertEqual(self.report(defence_a='HELD')['defence_rounds_run'], 2)
        self.assertEqual(self.report(defence_a='PENDING', defence_b='PENDING')['defence_rounds_run'], 0)

    def test_missing_receipt_not_measured(self):
        report = self.report(receipt_available=False, fee_wei='12')
        self.assertEqual(report['missing_receipts'], 1)
        self.assertEqual(report['terminal_receipts'], 0)
        self.assertEqual(report['briefs'], 0)
        self.assertEqual(report['fee_measured_receipts'], 0)

    def test_scenarios_do_not_merge_reused_brief_ids(self):
        records = [self.record(scenario=1, brief_id=0, status='NO_STATE_RECORD',
                               tx_status='UNDETERMINED', gate='', verdict=''),
                   self.record(scenario=4, brief_id=0, gate='UNDECIDABLE',
                               status='REJECTED', verdict='')]
        report = summarize(records, '0xcontract', 'bradbury')
        self.assertEqual(len(report['scenarios']), 2)
        self.assertEqual(report['scenarios'][0]['scenario'], 1)
        self.assertEqual(report['scenarios'][0]['gate'], '')
        self.assertEqual(report['scenarios'][1]['scenario'], 4)

    def test_reference_gate_failure_blocks_dependent_scenarios(self):
        failed = self.record(scenario=1, brief_id=0, call='open_brief',
                             status='NO_STATE_RECORD', tx_status='UNDETERMINED',
                             gate='', verdict='', judge_raw='',
                             defence_a='', defence_b='', forgery_attempted=False)
        report = summarize([failed], '0xcontract', 'bradbury')
        self.assertEqual(report['briefs'], 0)
        self.assertEqual(report['brief_attempts'], 1)
        self.assertEqual([s['scenario'] for s in report['blocked_scenarios']], [2, 3])
        self.assertTrue(all(s['depends_on'] == failed['tx'] for s in report['blocked_scenarios']))
        self.assertEqual(report['transactions'], 1)
        self.assertIn('cannot accept', report['scenarios'][0]['note'])
        self.assertTrue(any('Defence rounds run: 0' in line for line in report['honesty']))
        self.assertTrue(any('forged delivery not submitted' in line for line in report['honesty']))
        self.assertTrue(any('does not establish the cause' in line for line in report['honesty']))
        vague = dict(failed, scenario=4, status='REJECTED', gate='UNDECIDABLE',
                     tx_status='ACCEPTED', tx='0x' + 'c' * 64)
        report = summarize([failed, vague], '0xcontract', 'bradbury')
        self.assertEqual(report['briefs'], 1)
        self.assertEqual(report['brief_attempts'], 2)
        self.assertEqual(len(report['scenarios']), 2)
        self.assertEqual(len(report['blocked_scenarios']), 2)

    def test_failed_withdraw_preserves_rejected_brief(self):
        opened = self.record(scenario=4, brief_id=0, call='open_brief',
                             status='REJECTED', gate='AMBIGUOUS',
                             verdict='', judge_raw='', defence_a='PENDING',
                             defence_b='PENDING', forgery_attempted=False,
                             execution_result='FINISHED_WITH_RETURN', fee_wei='7')
        withdrawn = dict(opened, call='withdraw', status='NO_STATE_RECORD',
                         gate='', execution_result='FINISHED_WITH_ERROR',
                         tx='0x' + 'd' * 64, fee_wei='11')
        report = summarize([opened, withdrawn], '0xcontract', 'bradbury')
        self.assertEqual(report['scenarios'][0]['gate'], 'AMBIGUOUS')
        self.assertEqual(report['scenarios'][0]['status'], 'REJECTED')
        self.assertEqual(report['briefs'], 1)
        self.assertEqual(report['refused_by_gate'], 1)
        self.assertEqual(report['no_state_record'], 1)
        self.assertEqual(report['fee_total_wei'], '18')
        self.assertEqual(len(report['scenarios'][0]['transactions']), 2)
        self.assertEqual(report['scenarios'][0]['transactions'][-1]['execution_result'],
                         'FINISHED_WITH_ERROR')

    def test_decidable_reference_does_not_block_dependents(self):
        report = self.report(scenario=1, call='open_brief', gate='DECIDABLE')
        self.assertEqual(report['blocked_scenarios'], [])

    def test_collector_preserves_raw_evidence(self):
        tx = '0x' + 'b' * 64
        receipt = {'status': 'accepted', 'fee': '173300700', 'validators': ['v1'],
                   'execution_result': 'FINISHED_WITH_RETURN',
                   'enrichment_data': {'rounds': [{'round': 0, 'result': 'majority_agree'}]}}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = folder / 'manifest.jsonl'
            manifest.write_text(json.dumps({'tx': tx, 'brief_id': 2, 'scenario': 3,
                                           'forgery_attempted': True}) + '\n')
            cache = folder / 'cache.json'
            cache.write_text(json.dumps({tx: {'receipt': receipt, 'brief': {'status': 'SETTLED'}}}))
            out = folder / 'records.jsonl'
            subprocess.run([sys.executable, str(ROOT / 'scripts/collect_receipts.py'),
                            str(manifest), '--from-json', str(cache), '--out', str(out)],
                           check=True, capture_output=True)
            self.assertEqual(json.loads((folder / 'receipts' / (tx + '.json')).read_text()), receipt)
            record = json.loads(out.read_text())
            self.assertEqual(record['validators'], ['v1'])
            self.assertEqual(record['fee_gen'], '0.000000000173300700')
            self.assertTrue(record['forgery_attempted'])
            report = summarize([record], '0xcontract', 'bradbury')
            self.assertEqual(report['fee_total_wei'], '173300700')
            self.assertEqual(report['scenarios'][0]['transactions'][0]['validators'], ['v1'])
            # A failed open cannot inherit a later brief with a reused ID.
            receipt['execution_result'] = 'NONDET_DISAGREE'
            cache.write_text(json.dumps({tx: {'receipt': receipt, 'brief': {
                'status': 'REJECTED', 'gate': 'UNDECIDABLE'}}}))
            subprocess.run([sys.executable, str(ROOT / 'scripts/collect_receipts.py'),
                            str(manifest), '--from-json', str(cache), '--out', str(out)],
                           check=True, capture_output=True)
            failed = json.loads(out.read_text())
            self.assertEqual(failed['status'], 'NO_STATE_RECORD')
            self.assertEqual(failed['gate'], '')


if __name__ == '__main__':
    unittest.main()
