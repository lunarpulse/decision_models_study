---
name: Insurance Claims Decision Console
description: A calm, evidence-first visual system for following one claim across engines and training states.
status: final
colors:
  ink: '#1a2433'
  muted: '#5b6b7c'
  bg: '#eef1f5'
  card: '#ffffff'
  line: '#d7dee7'
  accent: '#1f5fa8'
  accent-soft: '#e8f0fa'
  ok: '#0b6e4f'
  warn: '#8a5300'
  warnline: '#d97706'
  bad: '#b91c1c'
  day1-soft: '#fff8ec'
  after-soft: '#f0f9f4'
typography:
  body:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
    fontSize: '16px'
    fontWeight: 400
    lineHeight: 1.5
  title:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
    fontSize: '32px'
    fontWeight: 700
    lineHeight: 1.2
  heading:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
    fontSize: '24px'
    fontWeight: 700
    lineHeight: 1.25
  label:
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
    fontSize: '14px'
    fontWeight: 600
    lineHeight: 1.4
rounded:
  sm: '8px'
  md: '12px'
  full: '999px'
spacing:
  '1': '8px'
  '2': '16px'
  '3': '24px'
  '4': '32px'
  '5': '40px'
  '6': '48px'
components:
  card:
    background: '{colors.card}'
    border: '{colors.line}'
    radius: '{rounded.md}'
    padding: '{spacing.2}'
  decision-table:
    background: '{colors.card}'
    border: '{colors.line}'
    cell-padding: '{spacing.1}'
  score-chip:
    background: '{colors.accent-soft}'
    foreground: '{colors.ink}'
    radius: '{rounded.full}'
  claim-card:
    background: '{colors.accent-soft}'
    border: '{colors.line}'
    radius: '{rounded.md}'
  preset-chip:
    background: '{colors.card}'
    border: '{colors.line}'
    radius: '{rounded.full}'
  story-strip:
    gap: '{spacing.1}'
    active-color: '{colors.accent}'
  reveal-button:
    background: '{colors.ok}'
    foreground: '{colors.card}'
    radius: '{rounded.sm}'
---

# Brand & Style

The console is a live teaching instrument, not a dashboard competing for attention. Keep the selected claim and the side-by-side decisions central; make the training reveal legible without theatrics. One neutral canvas, one consistent card style and restrained era color support the story. The Domain Builder and ops retain their behavior while inheriting shared visual foundations.

# Colors

Use {colors.bg} for the canvas, {colors.card} for surfaces, {colors.ink} for primary text, {colors.muted} for supporting text and {colors.line} for quiet boundaries. {colors.accent} and {colors.accent-soft} identify interaction and selected claim context. Day 1 uses {colors.warn}, {colors.warnline} and {colors.day1-soft}; After uses {colors.ok} and {colors.after-soft}. {colors.bad} indicates an incorrect answer or failure. Use a symbol and text as well as color for verdicts and states; never use amber or green alone to imply correctness or causation. Preserve readable contrast.

# Typography

Use the native {typography.body.fontFamily} stack, with no external fonts. The {typography.title.fontSize} title, {typography.heading.fontSize} section heading, {typography.body.fontSize} body and {typography.label.fontSize} supporting label create a clear hierarchy. Bold only the claim facts that the rules hinge on—policy type, dates, amount and documents—and meaningful table labels. Keep the answers and their manual comparator easy to scan.

# Layout & Spacing

Build with the {spacing.1} base scale: {spacing.2} card padding and routine gaps, {spacing.3} and {spacing.4} between larger groups. Tabs lead into the story strip, compact claim picker and highlighted claim card; the summary and decision table remain visually subordinate to the same-claim story. At a 390 px viewport, fit the page to the viewport, keep controls reachable without scrolling past a long preset list, and scroll a wide table inside its own wrapper rather than making the page scroll horizontally.

# Elevation & Depth

Favor borders and soft surface contrast over shadows. Cards use the same white surface, {colors.line} boundary and {rounded.md} corners. The tinted claim card and era highlights distinguish context, not a separate elevation tier.

# Shapes

Use {rounded.sm} for controls, {rounded.md} for cards and {rounded.full} for chips. Repeated shapes should make selection and comparison predictable rather than decorative.

# Components

- **Decision table:** one bordered table, seven decision rows grouped into four journey stages. Columns are the engines visible in the selected mode plus the claims manual. Answer and ✓/✗ are immediately scannable; confidence, probability bars and rules evidence appear on demand. After-mode changed rows use a restrained green treatment and a readable “was …” annotation.
- **Score chip:** compact {rounded.full} chip above the table for each engine, displaying `k/7` when a manual answer is available.
- **Claim card:** highlighted {colors.accent-soft} surface showing the actual selected claim, with rule-relevant facts in bold.
- **Preset chip:** compact, grouped standard, fraud and multilingual choices; selected and keyboard-focused states are distinct and legible.
- **Story strip:** four ordered steps below the tabs, with the current step visually highlighted: ① Pick a claim → ② Day 1: untrained engines → ③ After: trained on 12,000 past claims → ④ Compare all four. Training happened before the session, in about 15 minutes.
- **Reveal button:** prominent green control labeled “Show the same claim after training on 12,000 past claims →”; its wording does not imply live training.
- **Summary and fine print:** keep the headline holdout numbers in a slim row and the qualifications in an accessible disclosure.

# Do's and Don'ts

- Do preserve visible `:focus-visible` rings, text labels and non-color verdict cues; honor `prefers-reduced-motion`.
- Do keep the existing palette and ensure the table alone scrolls horizontally on narrow screens.
- Don't turn each engine into a separate competing card, leave probability bars permanently expanded, introduce new external assets or use color as the only explanation.
- Don't present holdout results or confidence as a guarantee. Explain the limits in fine print.
