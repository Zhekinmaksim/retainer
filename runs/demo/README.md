# Operational Bradbury demo — 22 September 2026

This is a separate demonstration using [`calibration/demo-brief.json`](../../calibration/demo-brief.json). It **does not replace** the original reference experiment in [`runs/README.md`](../README.md), where the reference gate ended UNDETERMINED and the dependent scenarios could not run.

The new spec judges only the submitted plain-text body, requires two exact case-sensitive strings, excludes external evidence and explicitly rejects claimed waivers. Its SHA-256 is `800290994dd31fd996bf8653d28042ee9364ddaba8929bc8be7d82ba4463c0fd`.

Contract: [`0xe53c01FF26a6787Af29499668e80502195A3447B`](https://explorer-bradbury.genlayer.com/contracts/0xe53c01FF26a6787Af29499668e80502195A3447B).

| Scenario | Brief | Observed outcome | What it establishes |
|---|---:|---|---|
| 1. Autonomous honest work | 1 | DECIDABLE → SETTLED; judge PASS, defence HELD / HELD | Agent accepted, composed and delivered work, then invoked judgment. 100000-wei fee plus 25000-wei stake credited to agent. |
| 2. Missing required strings | 2 | DECIDABLE → SETTLED; judge FAIL, defence HELD / HELD | Noncompliant delivery failed. Fee refunded internally and stake slashed to requester. |
| 3. Claimed waiver / forged PASS | 3 | DECIDABLE → SETTLED; judge FAIL, defence HELD / HELD | The judge was **not fooled**. The attack failed; this does **not** demonstrate the defence overturning a forged PASS. |
| 4. Vague specification | 0 | AMBIGUOUS / REJECTED | Gate refusal. Reuses the same existing live open and withdrawal receipts from the original run, not an additional execution. |

Six defence rounds executed on briefs 1–3. **Zero forgeries were demonstrated caught by the defence.** All three judgments remain subject to chain finalization at this snapshot. This narrow exact-string demo is not evidence that arbitrary real-world work can be safely adjudicated.

## Evidence

- [`bradbury.jsonl`](bradbury.jsonl): 15 GenLayer transaction hashes, with scenario labels. The two scenario-4 rows explicitly identify reused evidence.
- [`records.jsonl`](records.jsonl) and [`receipts/`](receipts/): collected state and raw explorer receipts.
- [`../../web/demo-report.json`](../../web/demo-report.json): generated report, separate from the original `report.json`.
- [`agent-decisions.json`](agent-decisions.json), [`agent-run.txt`](agent-run.txt), [`envelopes/`](envelopes/): actual decisions and submitted payloads. The honest brief ran with `retainer_agent.py --settle --manifest runs/demo/bradbury.jsonl` under the separate agent account.
- [`browser-journal.json`](browser-journal.json): actual accept, deliver and judge transactions for scenario 3, plus a failed EVM withdrawal attempt.
- [`browser-journal-retry.json`](browser-journal-retry.json): successful withdrawal submission after the interface added 50% gas headroom.
- [`browser-workspace-retry.png`](browser-workspace-retry.png): browser screenshot of real state and withdrawal receipt.

The successful agent withdrawal is [`0x279fbf04939dd30f69383eca05bacb20da42487f60bf54fe5019c842fb2409a6`](https://explorer-bradbury.genlayer.com/transactions/0x279fbf04939dd30f69383eca05bacb20da42487f60bf54fe5019c842fb2409a6). It reached ACCEPTED / FINISHED_WITH_RETURN and the agent's internal credit became zero. It emitted a 125000-wei transfer. **Its external transfer is not proven finalized by this snapshot.** ACCEPTED is provisional. The requester still has credits from the two FAIL settlements; they are not escrowed against open jobs.

## Browser verification

The real Chrome page connected through an EIP-1193 provider bridged locally to a test account held in the OS keychain. Browser clicks submitted actual Bradbury transactions. This exercised the browser SDK, signing interface, EVM-hash capture, consensus polling, delivery, settlement and withdrawal. Private keys never entered the page or the repository. This is not a claim that every browser-wallet extension was tested. The deployed site has no server signer and uses the visitor's wallet.

Read-only live RPC inspection, mobile layout, missing-wallet feedback and no uncaught JavaScript errors were also checked. See [`browser-check.json`](browser-check.json) and [`browser-check-retry.json`](browser-check-retry.json).

Two EVM submissions reverted before producing a GenLayer transaction ID: the first scenario-3 open attempt and the first browser withdrawal. They are retained in [`scenario3-open-submission-error.json`](scenario3-open-submission-error.json) and the browser journal. They are **not** counted as successful consensus receipts. Replaying their calls succeeded; gas estimates were close to gas used, so the browser now requests 50% headroom. This is a mitigation, not a proven diagnosis of every revert. No write is automatically retried. The open retry and buffered withdrawal subsequently succeeded.

## Rebuild

```bash
make demo-report CONTRACT=0xe53c01FF26a6787Af29499668e80502195A3447B
```

This refreshes statuses and may change ACCEPTED to FINALIZED later. It must not rewrite the original reference spec or delete failed attempts to make the narrative cleaner.
