# Retainer — design

> security paper with one held colour

The subject is escrow: money that sits still until a judgement resolves. So the
page is printed on the stock a bonded document is printed on — a pale
blue-green security paper, deep ink, a guilloche watermark that stops where the
reading starts, and perforated rules instead of hairlines.

One accent, and it carries exactly one meaning: **this money is not yours yet**.
Where the money ends up is shown by position, never by colour. That is why three
verdicts do not need three colours.

Colour is a resource, not a baseline. The accent **fills a surface in exactly
three places**: the coins while they are held, the gate output at the moment a
brief opens and the fee is escrowed, and the primary control that sets that in
motion. Everywhere else it is a stroke, a rule, or text — the marked call in the
cycle, a validator that read the spec cleanly, the empty-state rule, the
underline in the lede. If a fourth surface wants the accent, the answer is a
2px rule instead.

**Theme:** light. **Radius:** 0 everywhere — documents do not have rounded
corners. **Elevation:** none. Depth comes from tint steps and 1px rules; nothing
on this page simulates light.

## Tokens — colour

| Name | Value | Token | Role |
|------|-------|-------|------|
| Stock | `#DCE5E2` | `--stock` | Page canvas. Security-paper blue-green, not a grey. |
| Sheet | `#E6EDEA` | `--sheet` | The band a laid-on form sits in. A tint step, not a shadow. |
| Panel | `#F0F4F2` | `--panel` | Surface of the device, the console, the cycle cells. |
| Ink | `#0E2320` | `--ink` | Headings, body, the inverted honesty band. |
| Prose | `#3A4A46` | `--prose` | Supporting paragraphs. Never for headings. |
| Muted | `#6B7A75` | `--muted` | Labels, eyebrows, pan names. Never for a paragraph. |
| Rule | `#B9C7C2` | `--rule` | Perforation, borders, the guilloche stroke. |
| Rule soft | `#CBD6D2` | `--rule-soft` | Interior dividers inside a panel. |
| **Held** | `#2438C9` | `--held` | The only accent. Value in escrow, the active call, focus rings, links on hover. |
| Held wash | `#DFE3FA` | `--held-wash` | Surface of anything currently held; the marker under emphasised prose. |
| Slash | `#8A4A3A` | `--slash` | One word only: the `slashed` mark when a stake is taken. |

## Tokens — type

Three families and no more, and none of them chosen for being a trend. A monospace appears only on hex — addresses,
hashes, contract call names — and never on a label.

| Role | Family | Notes |
|------|--------|-------|
| Display and UI | Archivo | 500 headings, 700 wordmark and h1. Width axis 108–112 on the wordmark and the headline only |
| Prose | Spectral | 300, italic 300 for the pending state. Long measure, 1.58 line-height |
| Hex | DM Mono | 400/500. Addresses, hashes, call names. Never a label |

Each was picked from the subject rather than for novelty. Archivo is a grotesque
in the American gothic line, drawn for printing forms and newspapers at speed;
its width axis carries the wordmark and the headline, because expanded gothic is
the register of an engraved certificate. Spectral is a screen-first serif with a
dry, official cut — the voice of a document, not of an essay.

The previous set was Bricolage Grotesque, Newsreader and IBM Plex Mono. Bricolage
was chosen for not being Inter, which is the wrong reason: since 2022 it has
become the default "distinctive" grotesque and now reads as generated rather than
chosen. IBM Plex Mono was picked only because JetBrains Mono was taken by
[Suborn]. Neither answered the question the rest of this page answers, which is
what the subject is actually printed in.

Tracking tightens as size grows, because default spacing reads looser the
larger the type gets.

| Role | Size | Tracking | Token |
|------|------|----------|-------|
| display | `clamp(36px,4.1vw,49px)` | -.036em | `--t-display` / `--tr-display` |
| h2 | `clamp(27px,3.5vw,40px)` | -.028em | `--t-h2` / `--tr-h2` |
| h3 | 20px | -.018em | `--t-h3` / `--tr-h3` |
| lede | `clamp(19px,1.5vw,21.5px)` | -.012em | `--t-lede` / `--tr-lede` |
| body | 18px | — | `--t-body` |
| prose | 17px | — | `--t-prose` |
| small | 16px | — | `--t-small` |
| label | 14px | — | `--t-label` |
| micro | 12px | — | `--t-micro` |

Nine steps and no more. A size outside the scale reads as imported from another
system, which is precisely what twenty ad-hoc values looked like before they
were collapsed. The one exception is the wordmark at 22px, which is a logotype
rather than text.

Tabular lining numerals are on for the whole page. A ledger aligns its digits,
and every amount, count and hash on this page sits in a column.

## Layout

Max width 1180px, gutter `clamp(20px,5vw,72px)`. Everything left-aligned; prose
capped at 66ch, ledes at 43ch, headings at 22ch. Sections are separated by a
perforated rule and `clamp(46px,7vw,86px)` of air — one divider type, no
alternating bands.

The single exception is the honesty band at the foot, inverted to ink. It is the
one inversion on the page and it is spent on the part a reader is most likely to
skip.

## Motion

Motion answers an action; nothing loops for attention except the guilloche,
which drifts because paper under a light does. Every moving thing is inside
`@media (prefers-reduced-motion:no-preference)` — including the coins, which
otherwise travel 780ms across the board. Readers who ask for stillness get the
same final state, instantly.

The settlement device is where the boldness is spent. Everything else is quiet
on purpose — which only works if the controls are visible at the same moment the
device is. They live inside it, in a two-column foot under the board, with the
caption beside them.

The whole first screen — masthead, headline, lede, board, timeline and controls
— is budgeted to fit in roughly 600px of visible page, which is what a laptop
leaves after browser chrome and a dock. Anything added to the hero has to be
paid for out of that budget.

The headline is sized so that it sets in two lines at the hero column width, not
three. On a short laptop viewport the third line is the difference between the
controls being on the first screen and being below it, and a headline is not
worth a control.

The device takes the full measure rather than one column of the hero. Put a tall
device next to a short block of text and half the first screen is empty, and no
amount of rearranging inside that column fixes it. The headline and the lede sit
side by side above, ending on the same line; the board runs three pans across
below, with held in the middle so money starts at the centre and flies out to
one side. Coin geometry is CSS, keyed off `data-lane` and `data-slot`, so a
narrow screen can restack the board without the script knowing anything about
viewports.

## Do

- Spend `--held` on held value, the active call, and focus. Nothing else.
- Fill a surface with the accent only for held value, the moment of opening, and
  the primary control. A fourth candidate gets a 2px rule.
- Pick every size from the scale. If a component needs a size that is not in it,
  the component is wrong, not the scale.
- Show outcomes by position. Three verdicts, one colour.
- Keep radius at 0 and elevation at none. Tint steps and 1px rules do the work.
- Put the rehearsal label where the claim is made, not only in the footer.
- Name only contract calls that exist. `settle` is folded into `judge`.

## Don't

- Do not add a second accent, and do not colour-code the verdicts.
- Do not use `--muted` or `--slash` for anything longer than a few words.
- Do not use a shadow, blur, or white halo to fake depth.
- Do not put a monospace on a label; it belongs on hex.
- A mark that describes a pan (`slashed`) belongs on the pan's own line, not
  below whatever landed in it. Otherwise it competes with the coins for height
  and loses.
- Do not state a figure the receipts do not carry. Empty is a valid state and
  the page has one.

## Where this came from

The palette, the stock, the perforation and the clasp mark are drawn from the
subject: bonded documents and the act of holding value. The craft rules —
tracking that tightens with size, tabular numerals throughout, depth from tint
rather than elevation, a closed type scale, and colour rationed to named
surfaces — are common practice in financial-instrument interfaces and were
checked against published style references while building this. No colour, typeface, or component was taken
from another product's system; a page that reads as somebody else's brand would
undo the only thing this one is for.
