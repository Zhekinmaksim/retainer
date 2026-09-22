# GenLayer Portal — Project submission

Prepared for manual submission by the project owner. Paste the English fields below. The logo is `submission/logo.png` (512 × 512 PNG).

## Identity

**Project name:** Retainer

**Primary tag and topics:** select the closest available category for apps / payments / agent infrastructure. The portal's actual dropdown options were not provided; do not invent a tag. Suggested topics, if offered: escrow and AI agents.

## One-liner

Testnet escrow for agent work: GenLayer checks the acceptance spec, judges the delivery and challenges the verdict before crediting payment.

## Description

Retainer is a Bradbury testnet app for requesters commissioning work and agents delivering it. The requester pins an acceptance specification and escrows a fee; a different account stakes and submits an evidence envelope. A GenLayer Intelligent Contract checks whether the spec is decidable, judges the delivery and runs up to two adversarial verdict checks before settlement. PASS credits the agent; FAIL refunds the fee and slashes the stake; UNVERIFIABLE returns both deposits. Withdrawals are separate transactions.

The live browser app reads the contract, signs writes through your wallet and tracks consensus, execution and finalization. A Python agent can accept, deliver and settle suitable briefs autonomously. Public receipts separate the original UNDETERMINED reference experiment from a demo with explicit acceptance rules. This is a narrow research prototype: an unfooled judge does not prove the forgery defence works.

## How-to

### 01 — Inspect the existing live run

Open https://retainer-ashen.vercel.app/#workspace. No wallet is needed to read the ledger. Select Brief #1 to inspect its DECIDABLE gate, stored delivery, PASS settlement and HELD / HELD defence results. Select Brief #2 for noncompliant work and Brief #3 for the forged waiver: both settled FAIL, with HELD / HELD. The judge was not fooled. Select Brief #0 to inspect the AMBIGUOUS / REJECTED brief. Expand Published demo · receipts and outcomes below the workspace for receipts; the original reference experiment remains further down the page.

### 02 — Open your own brief

Connect an EIP-1193 browser wallet and switch to Bradbury (chain 4221). Fund it with test GEN for fees. Keep the prefilled demo specification, four probes, fee 100000 wei, stake 25000 wei and horizon 1000. Click Open & escrow fee and approve the wallet request. The journal shows the submitted hash and consensus / execution status. Once the gate is DECIDABLE and the brief is OPEN, note its ID. A rejected gate or UNDETERMINED transaction is a possible outcome; do not proceed as though it opened.

### 03 — Deliver from a second account

Switch the wallet to a different funded test account and reconnect. Select your new brief, click Accept & stake 25000 wei, and wait for successful execution and the ACCEPTED brief state. Click Use demo delivery, then Submit delivery. Wait until the brief is DELIVERED. The requester cannot accept their own brief.

### 04 — Judge and withdraw

Click Judge & settle. Inspect the verdict, both defence results and the wallet's credited balance. Successful completion with the unchanged demo body should produce PASS and a 125000 wei agent credit; consensus is not guaranteed. Click Withdraw credit. A wallet broadcast or ACCEPTED receipt is provisional: wait for FINALIZED with successful execution and inspect the recipient balance / transfer receipt. Reloading resumes journal checks; Resume status checks restarts paused polling.

## Expected verification outcome

Brief #1 shows DECIDABLE, SETTLED, PASS and HELD / HELD, with its stored delivery and public receipts. Brief #0 shows AMBIGUOUS / REJECTED. A fresh two-wallet run should record open, accept, deliver, judge and withdraw hashes; the unchanged demo body should credit 125000 wei to the agent. Verify successful execution and FINALIZED receipts. UNDETERMINED is a possible failure, not a successful settlement.

## Contract link

https://explorer-bradbury.genlayer.com/contracts/0xe53c01FF26a6787Af29499668e80502195A3447B

## Project links

**Website:** https://retainer-ashen.vercel.app/#workspace

**GitHub:** https://github.com/Zhekinmaksim/retainer

## Evidence links

Add the GitHub repository as the required evidence:

https://github.com/Zhekinmaksim/retainer

Additional supporting links:

- Operational demo: https://github.com/Zhekinmaksim/retainer/tree/main/runs/demo
- Receipt-backed demo report: https://retainer-ashen.vercel.app/demo-report.json
- Original reference experiment, including failure: https://github.com/Zhekinmaksim/retainer/blob/main/runs/README.md
- Live agent judgment: https://explorer-bradbury.genlayer.com/transactions/0x65a733b024141aa11af604e8bc7a890ec63fe2319038271fafef46e26ae21d54

## Optional demo video

Leave blank until a real video has been uploaded to YouTube or an X post. A screenshot or repository link is not a demo-video URL.
