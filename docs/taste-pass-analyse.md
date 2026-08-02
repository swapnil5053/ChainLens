# Taste pass: the Analyse surface

The mandatory loop for the three views, run before the first component was written. This
is a second pass, not a repeat: `docs/taste-pass.md` chose the visual language for the
product; this one decides the *layout argument* for a document-forward analysis screen,
which is a different question.

Skills applied, from the Brain repository: `design-system-setup`, `component-architecture`,
`frontend-states`, `frontend-structure`, `anti-ai-frontend`, `accessibility-audit`, and
`knowledge/frontend/interaction-motion.md` for motion.

---

## Brainstorm: three layout arguments

The visual language is settled (printed commercial instrument, paper ground, oxide ink,
hairline rules, tabular monospace for identifiers). What is not settled is what the screen
is *arranged around*. Three genuinely different answers, which cannot share a layout.

### Direction 1: Conversation-led

The query and answer own the screen. The contract is a drawer that opens when a citation
is clicked. Familiar, and the fastest to build.

**Rejected.** It is a chatbot with a document attached, and the brief says explicitly not
to build one. More concretely: it makes the contract the evidence *for* the answer, when
in a contract audit the contract is the artifact and the answer is the finding. An analyst
does not trust an answer they cannot see sitting inside the clause. Putting the document
behind a drawer charges a click for that trust step, every single time.

### Direction 2: Document-led, answer as marginalia

The contract is the page, at reading width, always visible. The answer arrives in the
margin beside the clause it cites, the way a reviewer writes in a margin. Citations are
not chips but marks in the text itself.

**Rejected, with one idea kept.** Marginalia cannot hold an answer of more than about
forty words at any usable measure, and answers here routinely quote a clause. It also has
no natural home for a second retrieval arm, which View 2 requires. The idea kept, and it
is the important one: **the citation mark lives in the document, not next to it.**

### Direction 3: Document-forward split, answer as a finding record

Two panes with the document dominant, and the answer rendered as a *record* rather than a
chat turn: a bordered field block with a tiny letterspaced label, the answer text, and a
numbered citation row underneath, exactly like the findings block on an inspection report.
The query box sits above the record, not at the bottom of a scroll.

**Chosen.** It matches the artifact the product imitates. It gives citations somewhere to
be numbered and hovered. It scales to the comparison view without redesign, because a
second arm is a second record column. And the document stays permanently visible, so the
trust step is free.

The three cannot share a stylesheet or a layout: one is a centred conversation column, one
is a single reading column with a narrow margin rail, one is a dominant-document split with
a bordered record block.

---

## Plan

### Layout

| View | Structure |
|---|---|
| Analyse | Split pane, document 62% / record 38% at >=1024px. The document is the primary pane and keeps its scroll position. Below 1024px it stacks, record first, document second, with a citation click scrolling the document into view. |
| Comparison | Two record columns over a shared query, each chunk row marked shared or unique. No document pane: this view is about the arms, not the text. |
| Latency | Single column. Four figures at `text-figure`, one stacked bar, and a per-phase table beneath. |

The 62/38 split is not a golden-ratio gesture. 62% of 1440px is about 890px, which at 17px
serif holds roughly 95 characters, the upper end of a comfortable measure for legal prose
full of long defined terms.

### Type and colour

Inherited from `docs/taste-pass.md` with one addition and one change.

**Addition:** the answer record uses the UI grotesque at 15px, not the document serif. The
answer is interface output; the contract is the document. Conflating them would let a
reader mistake a generated sentence for contract text, and that distinction is load-bearing
in an audit tool.

**Change:** tokens are restated in OKLCH, per the stack decision. Not cosmetic: the neutral
ramp is a single hue with lightness stepping, so a re-skin is one `--hue-neutral` value
rather than ten hand-picked hex codes. Ratios are recomputed by `scripts/contrast.py` and
recorded in `docs/accessibility-audit-web.md`.

### The citation, which is the whole product

- Citations render as bordered chips carrying a numeral and the clause label, not as
  bracketed text. A chip is a target; `[1]` is not.
- Hovering a chip raises the corresponding span in the document to a soft mark.
- Clicking scrolls the document pane and sets the span to the active mark: amber ground
  with a 2px oxide bar on both edges, per `.citation-mark[data-state="active"]`.
- Scroll is `scrollIntoView({ block: "center" })`, and the token layer forces
  `scroll-behavior: auto` under `prefers-reduced-motion`, so it jumps rather than glides.
- Keyboard: chips are in the tab order, the document pane is focusable so the marked span
  can be reached without a mouse, and the mark itself is clickable in the text.

### State placement, decided before building

Per `component-architecture`, ambiguity here is the bug factory.

| Data | Where it lives | Why |
|---|---|---|
| Contract list, contract text, analysis result, comparison result, latency aggregate | TanStack Query | server state, cacheable, refetchable |
| Selected contract id, active view, query text | URL search params | shareable and refreshable; a colleague should be able to open a link to a finding |
| Active citation index, hovered citation index | colocated `useState` | ephemeral, not worth a URL round trip |
| Nothing | global store | lifting has not hurt once, so no Zustand |

### State grid, per `frontend-states`

| View | Loading | Empty (first-use) | Empty (filtered / none) | Error | Partial | Ideal |
|---|---|---|---|---|---|---|
| Contract picker | 8 skeleton rows at the real 52px row geometry | not reachable, 29 contracts ship with the app; justified below rather than omitted | filter matched nothing: names the filter, offers clear | region error with retry, filter preserved | n/a | virtualized list |
| Document pane | skeleton paragraphs at prose measure | "No contract open" plus what picking one does | n/a | region error with retry, picker still usable | text renders before citations exist; marks appear when an answer resolves | marked prose |
| Answer record | skeleton matching the record geometry: label, three answer lines, two chip slots | "Nothing asked yet" plus three real example questions that run on click | "Nothing retrieved" naming the contract and suggesting the commercial term | region error inside the record, query preserved in the box | answer present, extractive note attached | answer with chips |
| Comparison | two skeleton columns, geometry matched | "No comparison run yet" | per-arm: "This arm returned nothing", the other column still renders | per-arm error, the other arm survives | one arm slower: it skeletons alone | both arms plus the overlap count |
| Latency | skeleton bar at final height, so no layout shift | "No latency samples yet" plus what to do | n/a | region error with retry | aggregate present, per-phase pending | figures, bar, table |

Two rules are implemented once, centrally: nothing appears before 300ms (`Delayed`), and a
refetch never blanks populated content (`keepPreviousData`).

### Motion

Three tokens, from `interaction-motion.md`: 120ms hover, 180ms enter, 90ms exit. Transform
and opacity only. What earns motion: the press acknowledgment on chips and buttons, the
citation mark changing state, and the answer record entering once when it first has
content. What does not: no stagger, no entrance animation on contract text, no transition
on view switch. `prefers-reduced-motion` collapses the duration tokens at the token layer,
so no component checks the preference.

### Performance

- Route-level splitting: the comparison and latency views are `React.lazy`.
- Motion is behind its own lazy boundary, because 27 kB gzipped for one 180ms transition
  does not belong on the critical path of a screen that has not animated anything yet.
- The contract list is virtualized with TanStack Virtual.
- The document renders as paragraph slices rather than one 50,000-character text node, so
  marking a span re-renders a paragraph.
- React Compiler is on. There is no manual `useMemo` or `useCallback` for memoisation in
  `src/`, and the verification step greps to prove it.

---

## Critique of the plan, before building

**1. A 62/38 split at 1440px leaves the record pane around 500px, tight for an answer plus
six chips.** Real risk of the chips wrapping into a ragged block. Resolved: chips render in
a labelled row that scrolls horizontally rather than wrapping, and the row reserves its
height whether or not chips are present, so the record never changes height when an answer
resolves. Reserved space is also what stops the hover affordance shifting layout.

**2. The comparison view shows per-query chunks from the mock adapter and a corpus-level
Recall@6 from the real evaluation.** Those have different epistemic status, and putting
them in one column invites a reader to think 0.475 was computed from the query they just
typed. Resolved: the Recall@6 figure carries its run id, the question count, and the phrase
"not over the query above" in bold. If that could not be made unambiguous the number would
come out of the view entirely.

**3. Virtualizing the document text conflicts with scroll-to-citation.** A virtualizer will
not have mounted the target paragraph, so `scrollIntoView` has nothing to scroll to.
Resolved: the document is not virtualized. Documents here top out near 90,000 characters,
roughly 400 paragraph nodes, which renders fine; virtualizing would trade a real feature
for an imagined problem. Only the contract list is virtualized.

**4. Two adapters behind one interface is where a mock quietly becomes the product.**
Resolved: the adapter in use is named in the footer at all times, every payload carries a
`source` field, and the footer renders MOCK or LIVE. A demo that cannot be mistaken for
live data is the only honest kind.

**5. The picker's first-use empty state is one I claimed cannot happen.** 29 contracts ship
as static fixtures, so the list can only be empty if the fixture fetch succeeds and returns
nothing. Justification recorded rather than omitted, per the skill, and the state is still
implemented, because half of "cannot happen" states turn out to be reachable within a
month.

---

## Critique of the build

Performed against the built application at 1440px and 768px, in both themes, reading the
markup and the bundle output. **No browser was available in this environment**, so this is a
code-and-artifact critique, not a visual one, and that limit is the first finding.

**1. Nobody has looked at it.** No screenshot exists. Every claim about how it looks is a
claim about markup and tokens, not about pixels. That is the largest weakness in this pass
and no amount of care in the other findings compensates for it.

**2. The comparison view carries the evaluation numbers well but the per-query divergence
is under-explained.** The smoke test shows the two arms return different chunk sets on 18 of
24 real query and contract pairs, which is the thing a viewer should notice first. The view
renders "N of 6 chunks shared" as a quiet chip in the corner. It should be a figure with the
same weight as the Recall delta, because the shared count is the part computed from the
query in front of them.

**3. The Analyse right-hand column stacks three blocks and scrolls as one.** Query box,
record, picker. At 900px tall the picker gets perhaps 200px, which is four rows of a
29-row list. A splitter, or moving the picker into a popover triggered from the document
header, would give the record and the picker room to be themselves. Not fixed.

**4. `answerDetail` is rendered as a quiet note under every answer.** It says the answer is
extractive and no model was called. That is correct and it is honest, but it appears on
every single answer in the same visual weight, and by the fifth query it is noise. It
should be attached to the data path chip in the footer once, not repeated per record.

**5. The extractive answer is the weakest content on the screen.** It quotes the top clause
and appends "Clause X also bears on this". That is a template, and with a real generation
provider it would be replaced wholesale. It is doing an honest job of demonstrating the
citation mechanism, but nobody should read it as a sample of what the product says.

**6. Fixture weight.** 2.4 MB of contract JSON in `public/`, of which the largest single
contract is 136 kB. Fetched lazily per contract, so it never lands on the critical path,
but it is 2.4 MB in the repository and it will grow linearly with the corpus. Beyond a few
hundred contracts the fixtures need to move behind the real API rather than being committed.
