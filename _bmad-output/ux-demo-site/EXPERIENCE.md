---
title: Decision Console whole-site experience
status: final
updated: '2026-10-28'
visual-system: DESIGN.md
---

# Foundation

This is one single-page web console: a presenter uses a laptop or projector and an audience follows on phones via the public URL. Its five modes are `?mode=day1`, `after`, `compare`, `ops`, and `domain`; absent or unrecognized mode currently opens ops. Preserve mode switching, browser history, deep links `?mode=domain&d=...`, script IDs, calls, polling, presenter-only gates, token prompts, reset and re-teach semantics. The three claim modes share one claim, not separate examples; ops is a measured portfolio, and Domain Builder is a separate live rule-change demonstration. [DESIGN.md](DESIGN.md) owns the visual tokens and shared classes; this document owns behavior. This is a restyle and reorganization only: keep existing content, numerical values, conditional states, features, caveats, and data provenance; do not invent results or actions.

# Information Architecture

All modes start with the shared product header: brand, five mode buttons and one service-status pill with the existing three service details on hover or keyboard focus. Below it, `.page-container` contains the mode-specific `.page-head`, mode content, and the existing footer with engine/training details, report link, local inference and version. Preserve the existing CTA placement and visibility: ops near the hero, day1/after before the footer, hidden for compare and domain.

## Day 1 — `?mode=day1`

1. Page intro and four-step claim story strip (pick, Day 1, After, Compare), including pre-session training time and current/reached markers.
2. Day 1 era panel explains untrained Laya and decider-4b; its reveal button carries the same claim to After.
3. Measured holdout summary and fine-print disclosure: Laya 46.4% → 100.0% average per decision and 1/500 → 500/500 all-seven; decider 70.8% and 21/500; rules 100% English only. Keep the 500 sealed claims, Wilson intervals, generator/shifted-phrasing caveat, rules `unparsed`, and uncalibrated confidence qualifications as supplied by the page, including dynamic unavailable states.
4. Claim picker: Standard, Fraud and Multilingual preset groups, paste-claim disclosure and run control. Choosing a preset runs it and collapses the picker; a summary and Change claim reopen it. Selected claim card emphasizes policy type, dates, amount and documents when present.
5. Exact request and questions schema disclosures, reading guidance, then seven-decision table grouped into four journey stages: Laya out-of-box and decider-4b beside the claims manual, score chips and one summary sentence. One toggle reveals confidence, probabilities, and available details. Show ✓/✗ only when the manual can judge.
6. Existing CTA and footer. The summary may remain above the picker as it is in the committed page; do not hide or alter its fine print.

## After — `?mode=after`

The same header, story, summary, picker, exact request, guidance and seven-row table, but the era panel explains that Laya was trained before the session on 12,000 past claims in about 15 minutes, and decider-4b remains untrained. Table columns are fine-tuned Laya, decider-4b and the manual. If Day 1 answers for the same claim exist, changed decisions are highlighted with `was …` and the count of changed decisions and those now matching the manual; otherwise explain that Day 1 is needed to compare. Reveal reruns the same claim in After; if no claim has run, select and run the first preset. Preserve language limitation and out-of-box fallback shown in After for non-English inputs.

## Compare — `?mode=compare`

The shared intro/story, compare era panel, holdout summary/fine print, picker, request disclosures and seven-decision table. Show Laya out-of-box, Laya fine-tuned, decider-4b, rules engine and claims manual; the score sentence names engines with complete 7/7 answers or explains unavailable scores. The shared details toggle includes rules evidence. The compare panel retains the English-phrasing limitation and `unparsed` behavior. CTA is hidden, footer stays. Selecting the tab retains the current results as the existing `setMode` does; it does not invent an automatic re-run.

## Ops — `?mode=ops`

Intro, existing measured hero line and CTA, then ops era explanation of the 500 sealed claims and dispositions. The ops content contains six dynamically calculated counter cards; engine selector, fraud cutoff τ slider and displayed value, annual volume input, illustrative projection and conditional certainty note; claim queue with disposition definitions, three view buttons, conditional reset-overrides action, table and footnote; then calibration bins and their caveat. Controls may be placed ahead of the six counters for a clearer cause → effect reading, while keeping all data and behavior unchanged. The six counters are total holdout/amount, straight-through count and amount, all-seven correctness of auto-paid claims, fraud paid and leaked dollars, fraud dollars held and false flags, and adjuster workload and amount. Projection is illustrative at the synthetic fraud mix; dollars held are for investigation, not savings. Preserve the measured and changing values rather than hard-coding example numbers.

The queue groups by **engine-proposed** disposition: adjuster review, flagged → SIU, auto-paid/spot-check. Each row includes claim, category, amount, routing, fraud probability, actual fraud/legit, predicted/gold touches, effective disposition, and Auto-pay/Flag fraud/To adjuster controls. Overrides update counters but remain in the original engine view, shaded and labeled with what the engine said. The existing top 14, ordering, empty view text and reset behavior stay. Calibration displays each engine's bins, actual fraud share and sample size, with sharp-probability caveat when applicable.

## Domain Builder — `?mode=domain`

1. Intro and domain era explanation; business picker for Support desk, Logistics exceptions and HR exceptions, each with description and fresh/re-taught badge. The initial picker includes the presenter-only reset-every-business action and the seven decisions, 2,000 past cases and 500 sealed cases context. A deep link selects its business; a live job can select the business being taught as today.
2. For a selected business show live activity if relevant, picker, five-step navigation and active-model state, including presenter reset for a re-taught business. The strip links to the existing acts; do not turn it into a wizard that blocks access.
3. **1 Your model today:** untrained versus production-model holdout stats, optional decider scale, production readiness note, one representative case and its seven decisions against the rulebook, with another-case and try-it actions.
4. **2 Change a rule:** the three existing policy cards and their editable dropdowns, today's-rule hints, impact on the 500 test cases and decisions, corpus/lesson counts, and the 24-case unseen exam (12 changed and 12 unchanged for the supplied examples). Exam tiles can open a case in step 5. If a selection is today's rule, say so and disable re-teaching.
5. **3 Re-teach:** presenter-only action and readiness explanation; while running, prepare → learn → exam phases, genuine progress, elapsed clock and the existing question to the room. Token is requested as currently; audience pages follow a running job but cannot initiate it without the token.
6. **4 What changed:** appears when a result exists: actual timing, rule and finish time, before/after changed and untouched results, fully right cases and optional out-of-box baseline, followed by exam tiles. Show real misses in red and keep their text/✗. Do not assume a perfect result.
7. **5 Try to break it:** editable case and existing one-click mutations, Ask the models, side-by-side answers and rulebook, score chips and latency; compare out-of-box and production models, plus the re-taught model when available. Changed rulebook decisions are annotated `was …`. For partially unreadable wording, explain the rulebook cannot referee and suppress verdicts/scores, while models still answer.
8. Fine print disclosure contains synthetic corpus, production training, re-teach counts and timings when available, same-generator/unseen-format limits, hand-reworded probes, sharp confidence and offline measured table. Keep reset and persistent fresh/re-taught states and the footer.

# Voice and Tone

Plain, specific and evidence-first: use “claims manual,” “rulebook,” “unavailable,” “can't read,” “no manual answer — judge yourself,” and existing action labels. The reveal describes historical training, whereas Domain Builder re-teaching is live. State measured denominators, synthetic and in-distribution limitations, English-only rules and fine-tune constraints, uncalibrated confidence, and actual misses. Never promise deployment accuracy, fabricate a comparator, or imply held dollars are saved. Preserve every existing caveat, explanatory detail and meaningful label when reorganizing.

# Component Patterns

Shared visual anatomy, sizing, breakpoints and semantic colors are defined in [DESIGN.md](DESIGN.md), e.g. {colors.accent-soft} selection, {colors.warning-soft} before/caution, {colors.success-soft} after/positive, {colors.danger-soft} wrong. Keep the original IDs and legacy classes needed by JavaScript as well as new shared classes. Component mapping below is a handoff contract, not permission to delete content or rewrite business logic.

| Mode | Today's element/class | Shared component and use |
|---|---|---|
| All | `.topbar`, `.brand`, `.tabs`, `button.tab`, `.dot` | `.app-header` with brand, `.app-nav` holding the same five `button.tab` IDs, `.status-pill` with the existing three dot nodes and service names in details. |
| All | `.wrap`, `.kicker`, `#heroTitle`, `#heroLead`, `#heroLine`, `#ctaHeroSlot` | `.page-container`, `.page-head` eyebrow/title/lead; preserve IDs and conditional hero/CTA placement. |
| All | `footer`, `.ctabar`, `.note`, `.callout` | Footer remains; existing CTA and notes use `.callout` with appropriate semantic modifier and existing contents. |
| Day 1 | `#storyStrip`, `.story-step`, `#era-day1`, `#revealBtn` | `.section` with step chips and `.card--warning`; reveal `.btn.btn--success`. Keep now/done text and pre-session context. |
| Day 1 | `#mainStats`, `.summary-row`, `.fine-print`, `.scell` | `.section`, compact `.stat` and score `.chip`; `details.disclosure` retains all summary caveats. |
| Day 1 | `#claimGrid`, `.preset-group`, `.preset`, `.preset-more`, `.paste-claim`, `.claim-card` | `.section`/`.card`, selectable `.chip`/`.chip--selected`, `details.disclosure`, labeled textarea and `.btn`; claim card is a contextual `.card--muted`. Preserve collapse and selection hooks. |
| Day 1 | `.asked`, `.schema`, `#decisions`, `.decision-table`, `.decision-detail`, `.verdict`, `.brow` | `details.disclosure`, contained code region, `.table-wrap > .table`, semantic badge/verdict and `.progress`; preserve grouped rows, toggle and all details. |
| After | `#era-after`, `#storyStrip .after` | `.card--success` and step chip; pre-session training text remains. |
| After | `.decision-table tr.changed`, `.was`, English-only `.note` | `.table` row `.is-changed` with `was …`, and `.callout--warning` for the language limitation. |
| Compare | `#era-compare`, `#mainStats`, `#claimGrid`, `.decision-table` | Neutral `.card`, `.stat`, `.chip`, `.disclosure` and `.table`; retain all four engine columns, manual, evidence and English-only caveat. |
| Ops | `#opsCounters`, `.statsgrid`, `.statbig`, `.statl` | Six `.card` + `.stat` / `.stat__value` / `.stat__label`; semantic card modifiers only for the actual result. |
| Ops | `#opsEngine`, `#tauSlider`, `#tauVal`, `#volIn`, `#opsProj`, `#tauNote` | Labeled native controls in a `.card`, projection text and conditional `.callout--warning`. |
| Ops | `#opsViews`, `.mini.on`, `#opsReset` | `.segmented` of compact `.btn` controls with explicit selected state; reset is `.btn--secondary.btn--sm` when present. |
| Ops | `.tablewrap`, `.opstable`, `tr.ovr`, `.chip-auto/.chip-rev/.chip-flag` | `.table-wrap > .table`, changed/override row treatment plus label; `.chip` modifiers appropriate to actual disposition; override buttons `.btn--sm`. |
| Ops | `.calrow`, `.calbin`, `#calCaveat` | `.section` with compact labeled bins, count text and caveat `.callout--warning` where present. |
| Domain | `.db-pick`, `.db-dom`, `.db-badge`, `.db-state`, `.db-live`, `#dbResetAll` | Selectable `.card` with existing radio semantics, `.badge`, state `.callout--success`/`--warning`, existing presenter `.btn`; preserve all text and reset gating. |
| Domain | `.db-steps`, `.db-act`, `.kicker` | Navigation with compact step buttons; each act `.section` + `.section-head` and `.card` where useful. Steps still scroll to acts. |
| Domain | `.db-vs`, `.db-stat`, `.db-impact`, `.db-chip` | `.stat` and `.chip` for comparison and impact; retain actual numbers, labels and selection distinctions. |
| Domain | `.db-pol`, `.db-card`, `.db-rule select`, `.db-today` | Selectable `.card` with existing radio/keyboard semantics and individually labeled native selects; today's-rule hint remains. |
| Domain | `.db-grid`, `.db-tile.chg/.win/.kept/.miss` | Interactive `.card` tiles with warning/success/danger state and text/✓/✗; activation still opens step 5. |
| Domain | `.db-go`, `.db-phases`, `.db-phase`, `.pbar`, `.db-clock`, `.db-ask`, `#dbTeachErr` | `.btn--success`, phase cards, labeled `.progress > .progress__bar`, `.stat` clock, `.callout` and `.status-line`; preserve live values. |
| Domain | `.db-try`, `#dbText`, `.db-mut`, `#dbAskBtn`, `.db-board`, `.db-dt`, `.db-fine` | Labeled textarea, segmented/chip-like mutation buttons and select, `.btn`, score `.chip`, `.table-wrap > .table` and `details.disclosure`; retain rulebook partial-read behavior and measurement content. |

# State Patterns

- **Loading:** retain current loading text for presets, claim run, portfolio, domain session, impact and model compare. `.skeleton` may accompany but never substitute for text; preserve current claim/domain and let available results render. Existing retry controls remain only where they already exist.
- **Unavailable:** engine cells say unavailable or no answer rather than wrong; other answers remain readable. Portfolio failure gives its existing Retry; studio failure names the unreachable service. Holdout summary reports unavailable instead of invented values.
- **English-only and unparsed:** fine-tuned Laya explains its English-only limit for multilingual examples; out-of-box Laya remains available. Rules say “can't read” rather than incorrect. In Domain Builder a partial rulebook read means no verdicts or scores for any decision on that wording.
- **Studio busy/training:** one re-teach at a time. A page follows a running job and its policy, disables the teach action and shows prepare/learn/exam, progress, clock and status. Compare may say the model is being re-taught; another business can show the live job and existing follow action. Do not fabricate progress or replace prior result until the existing flow does.
- **Warming up:** keep the existing studio warming-up explanation and automatic retry; first cold prediction may take about 1–2 seconds. Never label it a failed result.
- **Token and errors:** presenter uses the existing session-scoped studio token prompt for re-teach/reset. Wrong or missing token clears the stored value and reports rejection; a subsequent action prompts again. Preserve existing throttled, busy, lost/restarted, network and GPU-memory messages and the ready/no-production-model/unchanged-rule disabled explanations.
- **Fresh versus re-taught:** every business badge and selected-business state says what is active. Fresh means the production model only; re-taught names its rule and finish time. A successful re-teach starts from production and replaces the re-taught copy only on success; results persist across reloads. Audience pages follow state changes through the existing polling.
- **Reset:** existing confirmation and presenter token remain. Reset one or all deletes the re-taught model/result, not the production model; it is refused while re-teaching. Open pages follow the fresh state. Never present this as an undo of production training.
- **No data / no manual:** retain existing queue empty message, case-input prompt, no-manual explanation and conditional exam/result visibility. Do not show a placeholder as a result or mark unavailable data as wrong.

# Interaction Primitives

Mode buttons keep `role=tab`, existing IDs, `aria-selected`, controls relationships, URL/history semantics and selected-tab visibility. Presets run on selection, retain `lang` metadata and toggle expanded groups; paste uses the existing run button and empty-input prompt. Change claim restores focus, and reveal reuses the same claim. Details controls use native summary; the confidence toggle changes all decision details together. The status pill's service details are reachable on hover and keyboard focus without changing health polling.

Ops engine, τ, and volume immediately update existing calculations; view buttons choose the engine-proposed queue and override buttons apply actions without moving rows out of their original view. Domain business and rule cards retain radio semantics, enter/space activation and independently operable dropdowns; exam tiles open the chosen case, step buttons scroll to existing acts, mutations edit and ask as today. Reset keeps its confirmation and token prompt. Preserve all existing links, inputs, aria-live status regions, conditional states and API calls.

# Accessibility Floor

Keyboard users can reach and operate navigation, status details, disclosures, preset selection, controls, cards, exam tiles, tables and existing actions; focus is visibly indicated with the DESIGN.md ring. Give inputs and status indicators accessible names, expose current/selected/disabled state, and use semantic table headers and associated cell labels when claim decisions stack. Keep error and loading text available to assistive technology without interrupting input. Use ✓/✗, state names and `was …` as well as color; retain language attributes on multilingual claim text. Text and interactive affordances satisfy the DESIGN.md contrast floor. Respect reduced motion for tile animation, progress transitions and scroll while preserving completion. At 390px and 1366px avoid page-level horizontal overflow; contained scroll regions remain keyboard reachable and have descriptive accessible names.

# Key Flows

## Day 1 — Minji inspects the baseline

1. Minji opens the presenter's public Day 1 URL on her phone; service status, mode and current story step orient her.
2. The presenter selects a standard or fraud claim; the card presents its actual facts and the same seven decisions beside the manual.
3. **Climax:** Minji sees the baseline score and ✓/✗ against the manual, then reveals confidence/probabilities rather than mistaking confidence for correctness. She can open holdout fine print.

## After — Rafael sees what changed

1. Rafael follows that same selected claim from Day 1. The presenter presses the reveal; if none has run, the first preset is selected and run.
2. **Climax:** After reruns the claim and highlights changed fine-tuned decisions with `was …` and a textual count; the pre-session training note prevents confusion with live re-teaching.
3. Rafael opens the holdout caveats and understands that the measured 100% is not a deployment guarantee.

## Compare — Hana tests the limits

1. Hana opens Compare and reads all four engines against the same manual and claim, then exposes probabilities and rules evidence.
2. **Climax:** a multilingual example shows the fine-tune's English-only limitation and rules `unparsed` honestly, while out-of-box Laya can still answer.
3. The audience pastes a claim: without a manual answer the engines answer without a misleading verdict and the group judges for itself.

## Ops — Priya weighs the trade-off

1. Priya opens the ops floor and sees the 500-claim measured portfolio, its six counters and illustrative annual projection.
2. She switches from fine-tuned Laya, whose sharp 0/1 probabilities make τ ineffective, to zero-shot decider-4b, then changes τ to see throughput, leakage and customer friction move.
3. **Climax:** she overrides a claim, watches the counters change while the row remains in its engine-proposed view, and reads `engine said …`; Reset overrides restores measured routing. She checks calibration and its caveat.

## Domain — Alex changes a business rule

1. Alex picks a business, checks its fresh or re-taught badge, and sees the production baseline and one seven-decision case. A presenter selects a rule and reads impact plus unseen exam cases.
2. The presenter starts re-teach using the studio token; Alex follows prepare, learn and exam live, while the production model remains untouched.
3. **Climax:** the real result shows before/after changed and untouched decisions, including any misses; Alex chooses an exam case and compares out-of-box, production, re-taught and rulebook answers.
4. Alex tries a hand-reworded case and sees when the rulebook cannot referee. The presenter can confirm and token-authorize reset to fresh; the audience follows that state change.
