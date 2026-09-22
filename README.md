# Retainer

A labour market for agents where acceptance is judged by consensus, not by a
platform sitting in the middle.

Every escrow judges the answer. Retainer runs two checks nothing in this track
runs at all:

1. **Before the job opens** — the acceptance spec has to be decidable. A spec
   that two careful readers read two different ways is not a contract, it is a
   future dispute, and the brief is refused before any money is locked.
2. **Before the money moves** — the verdict has to survive hostile reading. A
   deliverable that flips the judge with text written inside it does not get
   paid when the embedded defence overturns the verdict. The judging prompt
   comes from Suborn's 44-attack, 10-class measurement; Retainer's adapted
   defence requires its own live evidence.

Retainer is the third contract in a trilogy that is already live on Bradbury.
Jastrow decides whether a question is answerable. Suborn cross-examines the
witness. Retainer holds the money until the verdict.

| | contract | what it does |
|---|---|---|
| [Jastrow](https://github.com/Zhekinmaksim/jastrow) | [`0xC8823fdeA01961D65b569D00C09c541E5615CC69`](https://explorer-bradbury.genlayer.com/contracts/0xC8823fdeA01961D65b569D00C09c541E5615CC69) | measures whether validators split on the same spec |
| [Suborn](https://github.com/Zhekinmaksim/suborn) | [`0xA8920A9Ee4027c8793F966045B38fea062491e91`](https://explorer-bradbury.genlayer.com/contracts/0xA8920A9Ee4027c8793F966045B38fea062491e91) | measures whether a spec survives adversarial evidence |
| Retainer | [`0xe53c01FF26a6787Af29499668e80502195A3447B`](https://explorer-bradbury.genlayer.com/contracts/0xe53c01FF26a6787Af29499668e80502195A3447B) | holds fee and stake, settles on the verdict |

## Live app and operational demo

[Open the Bradbury app](https://zhekinmaksim.github.io/retainer/app.html) to read
the deployed contract without a wallet, or connect two funded test accounts
to open, accept, deliver, judge and withdraw. The transaction journal saves
broadcast hashes, resumes on reload and distinguishes provisional consensus
from finalization and execution success.

A **separate, explicit acceptance spec** in [demo-brief.json](calibration/demo-brief.json)
opened successfully. The Python agent accepted brief #1, delivered its composed
body and settled with **PASS / HELD / HELD**. Brief #2, missing the required
strings, settled with **FAIL / HELD / HELD**. A forged waiver in brief #3 also
received **FAIL / HELD / HELD**: the judge was not fooled, so this does not
prove the defence can overturn a forged PASS. These results do not replace the
original reference experiment below. [Operational run notes](runs/demo/README.md)
and the [demo report](web/demo-report.json) record the full outcomes and limits.

For Portal submission, use the [prepared fields and review path](submission/portal.md).

## Original reference result — 22 September 2026

The reference brief did **not** open: its embedded gate transaction ended
[`UNDETERMINED`](https://explorer-bradbury.genlayer.com/transactions/0x167de357f5bd008c4d5371222f3c22da20b201f9f0f6c1c597b78fdcc70ee323).
There is no accepted gate verdict for this brief. The agent ran with `--settle`
and found no work to accept. Honest payment, spec-failure settlement and forged
delivery therefore remain untested on this specification.

The deliberately vague brief returned **AMBIGUOUS / REJECTED**
([receipt](https://explorer-bradbury.genlayer.com/transactions/0xe732478306e829a59e01f5aee6fefb9566ac0ae88526f77c15f4b1aa1b852530)).
The agent read it and declined: `not open (REJECTED)`.
**Zero live defence rounds ran in this original reference experiment.**
See the separate operational demo above for subsequent defence execution;
execution alone does not establish that an attempted forgery was caught.

[Full run notes](runs/README.md), [receipt-backed report](web/report.json),
[submission manifest](runs/bradbury.jsonl), and [raw receipts](runs/receipts/)
include failures as well as successful calls. Earlier deployment defects are
retained separately; they are not silently replaced by the latest run.

## How it differs from what already exists in this track

- **Apolo** checks freelance delivery evidence before payment. It judges the
  delivered result. It has no check that the acceptance spec was answerable.
- **MergeProof** does staked review and settlement, on pull requests only.
- **Internet Court** returns AI-jury verdicts after a dispute has already
  started. Retainer's whole point is that the dispute is prevented at open time.
- **GHBounty**, **Rally** pay on verified outcomes inside their own verticals.

All of them judge the answer. Retainer first checks that the question is
answerable, then that the answer cannot be forged.

## The cycle

```
open_brief  →  accept  →  deliver  →  judge  →  settle
    ↑ gate                    ↑ defence          ↑ money
```

- **open_brief** — the requester pins an acceptance spec, a closed answer
  vocabulary, a fee and the stake an agent must put up. The gate runs here. A
  spec that is not `DECIDABLE` produces a receipted brief in status `REJECTED`
  and the fee goes straight back. The job never opens.
- **accept** — an agent takes the brief and locks a stake. One agent per brief.
- **deliver** — the work is submitted as an evidence envelope. Judging sees the
  body byte for byte; dedup sees a flattened form.
- **judge** — consensus applies the pinned spec, then two independently framed
  referee rounds check that the answer is what a careful reader would reach
  anyway. Both rounds must agree. An unreadable round counts against the
  delivery.
- **settle** — `PASS`: fee to the agent, stake returned. `FAIL`: fee back to the
  requester, stake slashed. `UNVERIFIABLE`: everything goes back where it came
  from.

## The agent refuses work

The gate protects the requester. Nothing in the contract protects the agent, so
the agent protects itself, and it does so with the same shape the contract uses.

Before staking, it composes the deliverable and asks two questions. Does this
actually meet every requirement the spec names — because an unmet one is a FAIL
and a slashed stake. And would this survive the contract's defence — because a
deliverable that argues with its reader gets overturned whether or not anybody
meant to attack anything. A note to the reviewer, a quoted spec, a stray
zero-width character: all of them cost the fee on honest work.

Briefs it cannot answer are declined with the reason stated. It ships one
worker, for the campaign-post rule the trilogy was measured on, and says so
rather than guessing at specs it does not understand.

```bash
python3 agent/retainer_agent.py --address $CONTRACT --dry     # appraise only
python3 agent/retainer_agent.py --address $CONTRACT --settle  # work and settle
```

## Three verdicts, not two

`UNVERIFIABLE` credits the fee back to the requester and the stake back to the agent. Without a third
verdict the entire attack surface collapses to "make the deliverable unreadable
and get paid anyway". And nobody is punished on it, because punishing on
`UNVERIFIABLE` would hand an attacker a way to burn an honest agent's stake.

## How the gate and the defence are wired

They are implemented inside the Retainer contract, behind two wrappers,
`_decidable` and `_survives`. **Retainer does not make cross-contract calls to
Jastrow or Suborn.** The judging prompt is copied byte for byte from Suborn at
commit `9c7b0af`, and the referee framings are adapted from it, with each site
marked in the source.

The link to the two live contracts is evidential, not transactional: the full
Jastrow divergence measurement and the Suborn attack corpus are separate real
transactions against the deployed contracts, and their receipts are published
alongside. The embedded gate is a single-round approximation of a multi-round
measurement, and it is described that way everywhere it appears.

That distinction is deliberate. A demo that cannot fall over because of another
contract is worth more than an architecture diagram.

## Run it

```bash
make check
```

 assertions, no chain and no network. The suite is mutation-checked: breaking
any fail-closed rule, the settlement table, the gate or the dedup key turns it
red. What a stub cannot fake is validator disagreement, so every published
number comes from Bradbury receipts instead.

```bash
make dry          # rehearse all four scenarios against the local stub
make serve        # preview the page at http://localhost:8080
```

```
contracts/retainer.py        the contract: cycle, gate, defence, pull-accounting
cli/envelope.py              build, validate and hash retainer/1 envelopes
calibration/                 the reference brief, and the vague one the gate refuses
examples/                    the three delivery scenarios
agent/retainer_agent.py      an agent that works for money, and refuses briefs it cannot defend
scripts/gl_cmd.py            exact genlayer invocations, escaped, plus manifest lines
scripts/genlayer_write.mjs   SDK bridge for payable calls
scripts/collect_receipts.py  run manifest -> receipt-backed records
scripts/diagnose_missing.py  why a terminal transaction produced no state
scripts/build_report.py      records -> web/report.json, refuses fixtures
scripts/dry_run.py           the four scenarios offline, end to end
web/index.html               the page, driven entirely by web/report.json
web/DESIGN.md                the visual system, so the reel and the page cannot drift
test/run_tests.py            offline end to end suite
test/stub/genlayer.py        local GenLayer stand-in
DEPLOY.md                    what needs keys, and in what order
```

The publishing path refuses to lie on your behalf: `build_report.py` rejects
records with placeholder transaction hashes, refuses to write an empty live
report, and will not overwrite a receipt-backed report with a simulated or
dry-run one. Those refusals are themselves covered by the test suite.

The page carries no figures of its own. Without `web/report.json` it shows an
empty state saying nothing has run yet; with a stub snapshot it says so on the
page itself. Numbers appear only once receipts do.

Two things on it run in the browser: a rehearsal of the settlement table, and a
gate console you can type a spec into. Both are labelled as rehearsals at the
point where they make their claim, not only in a footer, and the test suite
checks those labels are still there. The console's three presets are checked
too, so the button marked "one that splits them" cannot quietly stop splitting
them.

## Status

Built for GenLayer Agent Tank, 3–17 September 2026. Track: Future of Work.

Nothing on this page is a simulated measurement. Numbers appear here only once
they are backed by receipts from Bradbury with real validator addresses.

## Licence

MIT.

## Run the browser app locally

```bash
npm ci
npm run build
make serve
```

Open `http://localhost:8080/app.html`. The app uses the pinned GenLayer JS SDK
and an injected EIP-1193 wallet. Signing keys stay in the wallet; there is no
server wallet. `npm run build` bundles the browser entrypoint; GitHub Pages
rebuilds and publishes `web/` on pushes to main. `make check` runs offline
contract, agent and receipt-pipeline checks.
