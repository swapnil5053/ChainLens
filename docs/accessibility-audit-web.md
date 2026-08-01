# Accessibility audit: the ChainLens web interface

WCAG 2.2 AA, audited before calling the work done.

**What was and was not verified.** Contrast is computed by `python scripts/contrast.py` and
is arithmetic, not judgement. Semantics, focus order and reduced motion were audited by
reading the built markup and the token layer. **No browser and no screen reader were
available in this environment**, so anything requiring observation is marked NOT VERIFIED
rather than passed. A PASS here follows from code that can be read; it is not a substitute
for someone tabbing through the thing.

## Contrast, computed

Produced by `python scripts/contrast.py --markdown`. Re-run it rather than trusting it.

**Light theme**

| pair | tokens | ratio | required | verdict | criterion |
|---|---|---|---|---|---|
| body text | `ink` on `ground` | 17.16:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| secondary text | `ink-muted` on `ground` | 6.97:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| field label, 11px | `ink-faint` on `ground` | 4.75:1 | 4.5:1 | PASS | WCAG 1.4.3, held to AA not large-text |
| citation accent on page | `accent` on `ground` | 6.66:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| citation accent on panel | `accent` on `panel` | 6.23:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| risk flag text | `flag` on `ground` | 5.83:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| marked span text | `ink` on `mark` | 13.32:1 | 4.5:1 | PASS | the citation mark must stay readable |
| control boundary | `rule-control` on `ground` | 3.05:1 | 3.0:1 | PASS | WCAG 1.4.11 |
| focus ring | `accent` on `ground` | 6.66:1 | 3.0:1 | PASS | WCAG 1.4.11 |

**Dark theme**

| pair | tokens | ratio | required | verdict | criterion |
|---|---|---|---|---|---|
| body text | `ink` on `ground` | 15.17:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| secondary text | `ink-muted` on `ground` | 7.51:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| field label, 11px | `ink-faint` on `ground` | 5.22:1 | 4.5:1 | PASS | WCAG 1.4.3, held to AA not large-text |
| citation accent on page | `accent` on `ground` | 6.65:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| citation accent on panel | `accent` on `panel` | 6.06:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| risk flag text | `flag` on `ground` | 9.22:1 | 4.5:1 | PASS | WCAG 1.4.3 |
| marked span text | `ink` on `mark` | 9.94:1 | 4.5:1 | PASS | the citation mark must stay readable |
| control boundary | `rule-control` on `ground` | 3.05:1 | 3.0:1 | PASS | WCAG 1.4.11 |
| focus ring | `accent` on `ground` | 6.65:1 | 3.0:1 | PASS | WCAG 1.4.11 |

Two judgement calls rather than arithmetic:

- `rule`, the decorative hairline, sits near 1.7:1 and is deliberately absent from the
  table. It separates rows whose meaning is carried in text, which 1.4.11 does not cover.
  Where a boundary carries meaning, `rule-control` is used and is in the table at 3.05:1.
- `panel` against `ground` is about 1.07:1 and is also absent, for the same reason. A panel
  is a grouping hint, never the only signal that something is interactive.

## Perceivable

| Criterion | Verdict | Evidence |
|---|---|---|
| 1.1.1 Non-text content | PASS | The one graphic, the latency bar, has `role="img"` and an `aria-label` naming every phase and its milliseconds. No decorative icons exist to need hiding: the interface has no icon set at all. |
| 1.3.1 Info and relationships | PASS | The latency table uses real `th[scope]`, a `caption`, `thead` and `tbody`. Contract and chunk lists are `ul` and `ol` with `li`. Each pane is a `section` with `aria-label`. |
| 1.3.2 Meaningful sequence | PASS | The Analyse grid uses `order-1` and `order-2` so the finding precedes the document on narrow screens and follows it on wide ones. The order classes move whole panes, not their contents, so DOM order matches reading order in both cases. |
| 1.4.1 Use of colour | PASS | The citation mark carries a 2px inset bar as well as a background tint. The comparison view labels each chunk `shared` or `unique` in text as well as marking the row edge. |
| 1.4.3 Contrast (minimum) | PASS | Computed above, both themes, every pair. The 11px label token is held to the 4.5:1 text requirement rather than the large-text exemption, which is why `ink-faint` is darker than the design wanted. |
| 1.4.10 Reflow | PASS | Single column below 1024px, no horizontal page scroll. Comparison columns stack. The citation chip row scrolls horizontally by design; it is a supplementary control strip and every chip it holds is also reachable by clicking the mark in the document. |
| 1.4.11 Non-text contrast | PASS | `rule-control`, on every control boundary, is tuned to 3.05:1 in both themes. The focus ring is the accent at 6.66:1 light and 6.65:1 dark. |
| 1.4.12 Text spacing | PASS | No fixed heights on text containers. The record and the chip row reserve minimum heights, not fixed ones. |
| 1.4.13 Content on hover or focus | PASS | Hovering a chip changes a mark state already on screen. Nothing appears in an overlay that must be dismissed. |

## Operable

| Criterion | Verdict | Evidence |
|---|---|---|
| 2.1.1 Keyboard | PASS by construction, NOT VERIFIED by use | Every interactive element is a real `button`, `input`, `textarea` or `a`. The document pane is `tabIndex={0}` so marked text is reachable. Enter submits, Shift+Enter inserts a newline. No key handler is attached to a non-interactive element. Nobody has actually tabbed through it. |
| 2.1.2 No keyboard trap | PASS | No modal, dialog or focus-trapping component exists. |
| 2.4.1 Bypass blocks | PASS | A skip link is the first focusable element and targets `#main`. |
| 2.4.3 Focus order | PASS | Source order is visual order within each pane; no positive `tabIndex` anywhere. |
| 2.4.6 Headings and labels | PASS | One `h1`, `h2` per pane, `h3` per comparison arm. Every input has a `label` with `htmlFor`. |
| 2.4.7 Focus visible | PASS | A designed 2px accent ring at 2px offset in the token layer, applied via `:focus-visible` to every interactive selector. The browser default is never relied on. |
| 2.4.11 Focus not obscured | PASS | No sticky overlay can cover a focused element; the footer is in normal flow. |
| 2.5.3 Label in name | PASS | A chip shows `1  Clause 14.3` and its `aria-label` begins "Citation 1, Clause 14.3", so the visible label is contained in the accessible name. |
| 2.5.8 Target size (minimum) | PASS | Buttons, tabs, the badge and the theme toggle are all `min-h-8` (32px). Contract rows are 52px. Citation chips are `min-h-6` (24px) with 8px separation. |
| 2.3.1 Three flashes | PASS | Nothing flashes. The whole application has one 180ms opacity and translate transition. |
| 2.3.3 Animation from interactions | PASS, NOT VERIFIED with the OS setting on | `prefers-reduced-motion: reduce` collapses the duration tokens to 1ms and forces `scroll-behavior: auto`, so scroll-to-citation jumps instead of gliding. Handled once at the token layer; no component checks the preference. |

## Understandable

| Criterion | Verdict | Evidence |
|---|---|---|
| 3.1.1 Language of page | PASS | `<html lang="en">`. |
| 3.2.1 On focus | PASS | Focusing a chip changes a mark's appearance in an already-visible region, not the context. |
| 3.2.2 On input | PASS | Typing changes nothing until submit. |
| 3.3.1 Error identification | PASS | Every failure renders an `ErrorRegion` with `role="alert"`, the message, and for a contract violation the offending field paths. |
| 3.3.2 Labels or instructions | PASS | Both query fields are labelled; placeholders are examples, not substitute labels. |
| 3.3.3 Error suggestion | PASS | Empty results suggest naming the commercial term rather than the concept. Disabled controls state the reason in `title` and, where there is room, in adjacent text. |

## Robust

| Criterion | Verdict | Evidence |
|---|---|---|
| 4.1.2 Name, role, value | PASS | Toggles carry `aria-pressed`, the active tab `aria-current="page"`, the selected contract `aria-current="true"`, loading regions `aria-busy`. |
| 4.1.3 Status messages | FAIL | The arrival of an answer is not announced. The record has no live region, so a screen reader user must navigate to it to discover that retrieval finished. This is the one substantive defect this audit found. |

## Findings

1. **4.1.3, FAIL.** The answer record should be `aria-live="polite"` so that the finding
   announces itself. Left open deliberately rather than bolted on untested: a live region
   that announces the wrong thing at the wrong time is worse than none, and there was no
   screen reader here to check it. It is the first thing to fix with a browser in hand.
2. **The citation chip row scrolls horizontally.** Accepted rather than fixed. Wrapping
   would change the height of the record when an answer resolves, and layout shift under
   the pointer is the worse failure. Every chip has a second route: the mark in the text.
3. **Three criteria are NOT VERIFIED** and are listed as such: the keyboard walk, reduced
   motion with the OS setting on, and any screen reader behaviour. They need a human with
   a browser.
4. **What the verification pass actually changed.** The criteria were applied while the
   components were written rather than retrofitted, so this audit found one defect rather
   than a list, and that is worth stating plainly rather than dressing up as fixes. The
   one real defect caught during verification was not an accessibility one: the smoke test
   showed that marked segments could not be checked against their citation because
   `Segment` carried no offsets. `start` and `end` were added to `lib/marks.ts`, which is
   what now lets a reviewer verify that a highlight sits inside the span it claims rather
   than taking the rendering on trust.
