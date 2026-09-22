# Bradbury live run — 22 September 2026

Current contract: [0xe53c01FF26a6787Af29499668e80502195A3447B](https://explorer-bradbury.genlayer.com/contracts/0xe53c01FF26a6787Af29499668e80502195A3447B).
Deployed source matches `contracts/retainer.deploy.py` byte for byte; SHA-256 and deployment transaction are in [deployment.json](deployment.json).

## Result

| Scenario | Live observation | Limit |
| --- | --- | --- |
| 1. Honest acceptance via agent | Reference `open_brief` ended `UNDETERMINED`; RPC result `DISAGREE`, explorer `majority_disagree` | No brief was created. Agent `--settle` scanned 0 briefs; no stake, delivery or payment occurred. |
| 2. Spec failure | BLOCKED by reference gate | Not submitted; no FAIL settlement or slash demonstrated. |
| 3. Forgery | BLOCKED by reference gate | Forged delivery not submitted, judge not tested, **0 defence rounds**. Inconclusive; no defence success claimed. |
| 4. Vague brief | `AMBIGUOUS`, stored `REJECTED`; agent declined it | Refusal demonstrated. A successful `withdraw` emitted a 100000-wei transfer; external delivery awaits finalization at the captured snapshot. |

The gate is measured first, without changing the reference specification to make it pass.
A transaction ending UNDETERMINED does not return a stored gate vocabulary answer.
Its status proves no accepted consensus outcome; it does not by itself prove why validators disagreed.
The trace captured for this version has empty stderr and result_code 0; it is diagnostic context, not an accepted state mutation.

### Evidence

- [Reference gate](https://explorer-bradbury.genlayer.com/transactions/0x167de357f5bd008c4d5371222f3c22da20b201f9f0f6c1c597b78fdcc70ee323)
- [Vague brief](https://explorer-bradbury.genlayer.com/transactions/0xe732478306e829a59e01f5aee6fefb9566ac0ae88526f77c15f4b1aa1b852530)
- [Withdrawal](https://explorer-bradbury.genlayer.com/transactions/0xfb572cc986ebc86858bbb727bd7b7445cc9e7765277a7a0070dc971757bc93be)
- [Submission manifest](bradbury.jsonl), [collected records](records.jsonl), [raw receipts](receipts/), [published report](../web/report.json)
- [Agent reference run](agent-reference.txt), [vague-brief refusal](agent-vague-decisions.json), [contract accounting](solvency.txt)
- [Reference RPC receipt](reference-rpc.txt), [execution trace](reference-trace.txt), [missing-state diagnosis](diagnosis.json)

The hero count covers the three scenario transactions on the current contract, excluding deployment and prior versions.
Fees in the report retain exact receipt wei and GEN strings. Validator addresses and raw receipt paths remain attached to every measured transaction.
`ACCEPTED` is distinct from `FINALIZED`; successful withdrawal execution does not prove an external transfer has finalized.

## Earlier deployments remain visible

1. [Initial SDK incompatibility](initial-sdk-error/README.md): absent `Address.ZERO` caused a runtime error. These receipts are **not** treated as a clean ambiguity measurement.
2. [Withdrawal SDK incompatibility](withdraw-sdk-error/README.md): reference gate ended UNDETERMINED; vague brief was AMBIGUOUS / REJECTED. Withdraw failed because Address was wrapped twice. The old immutable contract retains a requester credit of **100000 wei**; the new deployment does not recover it.

Both fixes leave the gate specification, prompts, equivalence principle, SDK dependency and settlement rules unchanged. The second and third deployments both observed UNDETERMINED on the same reference gate; all receipts are retained rather than selecting a favourable outcome.

## Reproduce the report

```bash
make report CONTRACT=0xe53c01FF26a6787Af29499668e80502195A3447B
```

Recollection refreshes statuses and fees from explorer, and the current brief state from chain. The immutable submission manifest remains separate from receipts. No simulated report is published.
