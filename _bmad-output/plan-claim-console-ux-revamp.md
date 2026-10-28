---
title: 'Claim console UX/UI revamp (day1 · after · compare)'
type: 'feature'
ticket: ''
created: '2026-10-28'
status: 'done'
baseline_revision: 'f1fdb753f78f210651478be7bdf00cb4b02a59ad'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The claim console (`?mode=day1|after|compare`) is cluttered: three stat cards, a long preset list, a free-text box, a collapsed request, per-engine cards with probability bars per question, a top-bar scoreboard and a legend all compete. The audience cannot see at a glance what changed between "untrained" and "trained", and the reveal button says "Train…" although training happened before the session. The Domain Builder's one-case, side-by-side comparison landed with the user; the claim console should feel the same.

**Approach:** Re-shape the three modes into one guided story around a single claim: pick a claim → see each engine's seven decisions side by side in one decision table against the claims-manual answer → reveal the trained model on the same claim with changed decisions highlighted → compare all four engines in the same table. Refresh the visual system (spacing, type scale, cards, focus, responsive) once, shared by every mode.

## Boundaries & Constraints

**Always:** keep every measured number and caveat that is on screen today (46.4/100/70.8 %, all-7 counts with Wilson CI, CAVEAT_100, english-only note, rules `unparsed` note, uncalibrated-confidence caveat); keep `?mode=` URLs, tabs and `setMode` contract; keep `/predict`, `/dec/predict`, `/rules` request shapes; keep the existing palette tokens (amber = day 1, green = after) and Domain Builder/ops behaviour; probabilities stay available on demand; multilingual presets keep `lang` attributes; mobile 390 px with no page-level horizontal overflow.

**Never:** change services, data files or numbers; remove the free-text input; add frameworks, fonts from CDNs or external assets; restart services or touch the tunnel; claim measurements not in the repo.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Day 1 preset | preset picked in day1 | decision table: Laya out-of-box · decider-4b · manual answer, ✓/✗ per cell, per-engine score chip k/7 | none |
| Reveal with claim | claim shown in day1, press reveal | switches to after, re-runs same claim, rows where trained answer differs from day-1 answer are highlighted with "was …" | engine down → "unavailable" cell, others render |
| Reveal without claim | no claim yet | first preset is selected and run, then after mode | none |
| Compare | any claim | one table, four engine columns + manual; rules evidence on demand | rules unparsed → "can't read" cells, note shown |
| Free text | pasted text, no gold | table with answers only, no ✓/✗, "no manual answer — judge yourself" | empty text → inline prompt |
| Non-English preset | KO/JA/HI/ES | fine-tuned column shows english-only note, Laya zero answers | — |
| Phone | 390 px wide | table scrolls inside its wrapper; page does not | — |

</frozen-after-approval>

## Code Map

- `demo-insurance/index.html:8-209` -- CSS tokens/components; refresh shared visual system here, keep `db-*` and ops classes working.
- `demo-insurance/index.html:213-321` -- topbar, hero, tabs, era panels, stats, claim grid (`#presets`, `#freeText`, `#runBtn`, `#askedState`, `#engines`), `#readHint`, footer. Restructure claim console markup.
- `demo-insurance/index.html:326-415` -- `ENGINES`, `MODE_ENGINES`, `QTITLE`, `HERO`, `applyHero`, `modeFromLocation`, `setMode` (keep signature; reveal path uses `setMode("after", true)`).
- `demo-insurance/index.html:417-562` -- `verdictFor`, `allCorrect`, `barsHTML`, `answerText`, `renderEngineCards`, `buildCompareMatrix`, `tallyEngine`, `drawScores`; replace card/matrix rendering with one decision-table renderer used by all three modes.
- `demo-insurance/index.html:564-647` -- `runClaim` (parallel fetches, keep), `loadPresets`, handlers for presets/free text/reveal/tabs.
- `demo-insurance/index.html:~650-890` ops floor, `~895-1640` Domain Builder -- do not change behaviour; only inherit shared visual tokens.
- `demo-insurance/DEMO_MANUAL.md` §3 steps 1–5 -- presenter script for these modes.

## Tasks & Acceptance

**Execution:**
- [ ] `demo-insurance/index.html` -- visual system refresh + claim-console restructure + unified decision table + reveal diff + responsive/focus/reduced-motion -- one owner, single file.
- [ ] `_bmad-output/ux-claim-console/DESIGN.md`, `EXPERIENCE.md` -- BMad UX spines describing the result.
- [ ] `demo-insurance/DEMO_MANUAL.md`, `demo-insurance/DEVELOPMENT_LOG.md`, `demo-insurance/README.md` -- presenter script, Phase 11 entry, audience-flow section.

**Acceptance Criteria:**
- Given day1 with a preset, when it runs, then one table shows both engines and the manual answer with ✓/✗ and per-engine k/7.
- Given a day1 result, when reveal is pressed, then after mode shows the same claim and highlights decisions that changed versus day 1.
- Given compare, when a claim runs, then all four engines appear in one table and rules evidence is reachable.
- Given a 390 px viewport, then no page-level horizontal scroll and the primary action is reachable without scrolling past the presets list.
- Given keyboard navigation, then tabs, presets and run controls show a visible focus ring; reduced-motion disables pulsing.
- Given ops or domain mode, then behaviour and numbers are unchanged.

## Implementation Notes

- Built in three subagent passes on `demo-insurance/index.html` (restructure; polish: wrapped chips, formatted manual answers, one detail toggle, headline sentence, story-step state, phone cards, scrolling tabs; compaction: "+N more" groups, collapsed "Claim: … · Change claim", CTA above footer).
- Removed IDs `sboard`, `resetScores`, `compareMatrix`, `cardFt`, `engines`; added `storyStrip`, `claimCard`, `decisions` and summary IDs. No dangling references.
- Verified through the public tunnel at 1366 and 390 px: fraud, Korean and pasted claims; zero page errors; no page-level overflow; ops and domain unchanged. Docs: DEMO_MANUAL §3, README, DEVELOPMENT_LOG Phase 11 + ledger #24, UX spines in `_bmad-output/ux-claim-console/`.

## Plan Change Log

## Review Triage Log

## Verification

**Commands:**
- extract `<script>` and parse with `new Function` -- expected: no syntax error.

**Manual checks (if no CLI):**
- Browser through the tunnel: day1 → reveal → after → compare on a preset, a Korean preset and free text; desktop 1366 and phone 390; screenshots; zero page errors; ops and domain still render.
