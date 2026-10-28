---
title: Claim console experience
status: final
visual-system: DESIGN.md
---

# Foundation

A single-page web console supports a presenter on a laptop and an audience following on phones through the public URL. Its claim modes (`?mode=day1`, `?mode=after`, `?mode=compare`) teach one claim by comparing seven decisions, not by switching among unrelated examples. [DESIGN.md](DESIGN.md) owns visual identity and tokens; this document owns behavior. The ops (`?mode=ops`) and Domain Builder (`?mode=domain`) experiences retain their existing behavior.

# Information Architecture

1. **Tabs:** preserve the mode URLs and switching contract. Day 1, After and Compare select which engine columns appear; ops and Domain Builder remain available.
2. **Story strip:** immediately under the tabs, show ① Pick a claim → ② Day 1: untrained engines → ③ After: trained on 12,000 past claims → ④ Compare all four, with the current step highlighted. Training happened before the session and took about 15 minutes.
3. **Claim picker:** compact preset chips grouped as standard, fraud and multilingual, plus a collapsible “paste your own claim” box and run control. A highlighted card displays the selected claim, emphasizing policy type, dates, amount and documents when present.
4. **Summary and fine print:** a slim row reports Laya 46.4% → 100.0% average per decision and 1/500 → 500/500 all-seven, decider 70.8% and 21/500, and rules 100% for English only. Fine print retains the holdout and Wilson confidence intervals for all-seven counts, the caveat on the 100% result and in-distribution evaluation, English-only and rules `unparsed` limitations, and the uncalibrated-confidence caveat.
5. **Decision table:** seven decisions in four journey-stage groups, with the claims-manual answer and one column for each visible engine. Day 1: Laya out-of-box and decider-4b. After: Laya fine-tuned and decider-4b. Compare: Laya out-of-box, Laya fine-tuned, decider-4b and rules engine. A score chip per engine sits above the table when a manual answer exists.

# Voice and Tone

Speak plainly and precisely: “claims manual,” “unavailable,” and “no manual answer — judge yourself” explain what the audience can and cannot conclude. The reveal says “Show the same claim after training on 12,000 past claims →”; it never suggests training is happening live. Describe holdout performance and uncalibrated confidence as measured evidence with limitations, not a guarantee.

# Component Patterns

- **Preset chips and claim card:** selecting a preset provides the claim to run; the card shows the same text and uses bold for rule-relevant facts. Preserve language metadata on multilingual presets.
- **Decision table:** show each engine answer next to ✓/✗ against the manual; put `k/7` scores above the table and one plain sentence saying what they mean (Day 1: who gets how many; After: how many decisions training changed and how many now match; Compare: who gets 7/7). One "Show confidence & probabilities" toggle reveals bars (and rules evidence in Compare) for every cell at once. Below 760 px the table becomes stacked per-decision cards. Use {colors.line} for boundaries and {colors.accent-soft} for claim context.
- **Picker collapse:** groups show three chips plus "+N more"; after a claim runs, the picker collapses to "Claim: … · Change claim" so the claim card and table sit near the top.
- **Reveal:** switch to After and re-run the same claim. Highlight each fine-tuned answer that differs from that claim's Day 1 Laya answer and label it “was …”. Use {colors.after-soft} for the changed-row treatment, with text rather than color alone conveying the change. If no claim has been run, select and run the first preset before showing After.
- **Fine print:** a disclosure keeps caveats accessible without competing with the single-claim comparison.

# State Patterns

- **Loading:** communicate that the claim is being run, while preserving its identity and the current mode; results appear as they are available.
- **Engine unavailable:** show “unavailable” in the affected engine's cells; other engines still render. Do not represent an unavailable result as an incorrect answer.
- **English-only:** for Korean, Japanese, Hindi or Spanish presets, the fine-tuned column explains its English-only limitation; Laya out-of-box answers using its multilingual routing. Retain each preset's `lang` attribute.
- **Free text without a manual answer:** show engine answers without ✓/✗ or a misleading `k/7` score, and say “no manual answer — judge yourself.” Empty text prompts inline rather than submitting an empty claim.
- **Rules unparsed:** show “can't read” in the relevant rules cells and explain the `unparsed` limitation, not a fabricated answer or an incorrect verdict.

# Interaction Primitives

Tabs and preset chips are keyboard-operable controls. A disclosure opens the paste box, another opens fine print, and cell expansion exposes details without requiring every bar to be shown at once. The run control submits the selected or pasted claim. The reveal carries the same claim across modes; selecting Compare runs the current claim in the four-engine table. Engine failure does not prevent the other answers from being read.

# Accessibility Floor

Every interactive control, including tabs, presets, run, reveal and disclosures, has a visible `:focus-visible` ring and a usable keyboard interaction. Convey current step, verdicts, changed answers and errors with text or symbols as well as color. Respect `prefers-reduced-motion`, including disabling pulsing. Preserve language attributes on multilingual content. At 390 px width the page has no horizontal overflow; wide tables scroll inside a labeled wrapper, and the primary action remains reachable without a long preset list.

# Key Flows

## Minji follows the same claim

1. Minji, a claims-operations director in the audience, opens the presenter's public URL on her phone. The tabs and current story step orient her without losing the claim.
2. The presenter chooses one standard preset and runs it in Day 1. Minji reads the highlighted policy, dates, amount and documents, then compares Laya out-of-box and decider-4b with the claims manual across seven decisions. The sentence above the table and the score chips summarize; she turns on confidence & probabilities to inspect them.
3. **Climax — the reveal:** the presenter selects “Show the same claim after training on 12,000 past claims →”. The same claim is re-run in After; changed fine-tuned answers are highlighted with “was …”. Minji sees what changed, while the strip explains the training was completed before the session.
4. In Compare, Minji reads the four engines and manual side by side, opening rules evidence where useful. She checks the summary and opens fine print before drawing conclusions from the holdout numbers.
5. The presenter tries a multilingual preset: out-of-box Laya answers, the fine-tuned column explains its English-only limit, and unparsed rules are labeled honestly. Minji then suggests a pasted claim; with no manual answer, the audience judges the answers without verdicts.
