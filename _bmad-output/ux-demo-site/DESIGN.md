---
name: Decision Console whole-site design system
description: Shared visual contract for the claim console, ops floor, and Domain Builder.
status: final
updated: '2026-10-28'
colors:
  bg: '#eef1f5'
  surface: '#ffffff'
  surface-muted: '#f6f8fa'
  border: '#d7dee7'
  text: '#1a2433'
  text-muted: '#526172'
  accent: '#1f5fa8'
  accent-soft: '#e8f0fa'
  success: '#0b6e4f'
  success-soft: '#f0f9f4'
  warning: '#8a5300'
  warning-soft: '#fff8ec'
  warning-border: '#d97706'
  danger: '#b91c1c'
  danger-soft: '#fdf4f4'
typography:
  sans: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
  mono: 'ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace'
  xs: '12px'
  sm: '14px'
  base: '16px'
  lg: '18px'
  xl: '20px'
  2xl: '24px'
  3xl: '32px'
rounded:
  sm: '6px'
  md: '8px'
  lg: '12px'
  pill: '999px'
spacing:
  '1': '4px'
  '2': '8px'
  '3': '12px'
  '4': '16px'
  '5': '20px'
  '6': '24px'
  '7': '32px'
  '8': '40px'
components:
  container: {max-width: '1180px', padding: '{spacing.4}'}
  header: {min-height: '64px', background: '{colors.surface}', border: '{colors.border}'}
  card: {background: '{colors.surface}', border: '{colors.border}', radius: '{rounded.lg}', padding: '{spacing.4}'}
  button: {radius: '{rounded.md}', min-height: '40px', padding-inline: '{spacing.4}'}
  chip: {radius: '{rounded.pill}', padding: '4px 12px'}
  table: {cell-padding: '8px 12px', border: '{colors.border}'}
  focus: {outline: '3px solid #1f5fa8', offset: '3px'}
---

# Brand & Style

A live, evidence-first enterprise console, not three prototypes or a marketing dashboard. Calm neutral surfaces, clear type and one blue interaction accent keep the claim, operational consequences, and business rule in focus. Color is reserved for meaning: amber before/Day 1 or caution, green after/positive, red wrong or failure. A re-taught active state is amber because it identifies a changed state, not a failure; fresh is green. Never infer correctness from era color. Use text or ✓/✗ as well as color.

Use no external font, CDN, framework, dark mode or decorative emoji. Keep functional ✓/✗. Replace language flags with KO, JA, HI, ES text codes alongside their existing labels and language metadata. Mode, business and rule icons may be omitted or replaced by small, monochrome inline SVG (`aria-hidden="true"` when adjacent text names the thing); do not add icon-only actions. Preserve all meaning, source data, labels, numbers, caveats, flows, service calls, URLs, IDs, gating and reset/re-teach behavior. [EXPERIENCE.md](EXPERIENCE.md) owns behavior.

# Colors

`theme.css` owns the following exact custom properties. Values mirror frontmatter and preserve the prior console palette; reference them rather than hard-coding mode-specific palettes.

```css
:root {
  --color-bg: #eef1f5;
  --color-surface: #ffffff;
  --color-surface-muted: #f6f8fa;
  --color-border: #d7dee7;
  --color-text: #1a2433;
  --color-text-muted: #526172;
  --color-accent: #1f5fa8;
  --color-accent-soft: #e8f0fa;
  --color-success: #0b6e4f;
  --color-success-soft: #f0f9f4;
  --color-warning: #8a5300;
  --color-warning-soft: #fff8ec;
  --color-warning-border: #d97706;
  --color-danger: #b91c1c;
  --color-danger-soft: #fdf4f4;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-pill: 999px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 40px;
  --shadow-sm: 0 1px 3px rgba(20, 30, 50, .06);
  --shadow-md: 0 4px 12px rgba(20, 30, 50, .10);
  --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
  --text-xs: 12px;
  --text-sm: 14px;
  --text-base: 16px;
  --text-lg: 18px;
  --text-xl: 20px;
  --text-2xl: 24px;
  --text-3xl: 32px;
  --ink: var(--color-text);
  --muted: var(--color-text-muted);
  --bg: var(--color-bg);
  --card: var(--color-surface);
  --line: var(--color-border);
  --accent: var(--color-accent);
  --accent-soft: var(--color-accent-soft);
  --ok: var(--color-success);
  --warn: var(--color-warning);
  --warnline: var(--color-warning-border);
  --bad: var(--color-danger);
  --era1: var(--color-warning);
  --era1-soft: var(--color-warning-soft);
  --era2: var(--color-success);
  --era2-soft: var(--color-success-soft);
}
```

Use {colors.text} on {colors.surface} and {colors.bg}; supporting text uses {colors.text-muted}. Colored text uses its dark semantic token on its matching soft surface. Reserve {colors.accent} for links, interactive focus and selection, not a competing category of results. Ensure normal text meets 4.5:1 contrast and large text and essential graphical boundaries 3:1; do not put white text on amber. Disabled controls remain legible.

# Typography

Body is `--font-sans`, `--text-base`, weight 400, line-height 1.5; no font downloads. Page title is `--text-3xl`/1.2, weight 700; section title `--text-2xl`/1.25, weight 700; subsection `--text-xl`/1.3, weight 600–700. Labels use `--text-sm`/1.4 and weight 600; eyebrow uses `--text-xs`, weight 700, uppercase and .08em tracking. Small caveats are at least `--text-xs`/1.4. Stats use `--text-2xl`–`--text-3xl`, 700, tabular numerals. Code/JSON uses `--font-mono`. At phone widths page titles may reduce to `--text-2xl`; never truncate meaningful caveats.

# Layout & Spacing

`.page-container` centers content at max-width 1180px with 16px inline padding; all grid children need `min-width:0`. Header minimum height is 64px on desktop, with brand, navigation and status arranged in one responsive row when space permits; it may grow rather than overlap. Page intro precedes mode content. `.section` groups content with 32px vertical separation; `.section-head` has a 16px lower gap. Standard cards use 16px padding, 8–16px internal gaps; larger group gaps are 24px. Use {spacing.1}–{spacing.8} consistently rather than unrelated spacing.

At ≤760px use 12px container/card padding, 24px section separation, a non-sticky header, and a single-line horizontally scrollable `.app-nav` (tabs never shrink; selected tab brought into view). Header elements may wrap. Full-width primary and secondary page-action buttons on phones; compact controls inside segmented groups, table rows, nav and chips retain intrinsic widths so their grouping stays usable. Claim decision tables stack by decision with visible per-cell labels; ops and Domain Builder tables remain semantic tables with contained horizontal scroll in `.table-wrap`. Collapse multi-column domain comparison, impact and try layouts to one column; Domain Builder step navigation becomes non-sticky. No page-level horizontal overflow at 390px or 1366px. Use wrapping, `min-width:0`, and contained table/code scrolling; never clip content.

# Elevation & Depth

Borders and surface contrast are the default; `--shadow-sm` is optional on cards and `--shadow-md` reserved for a floating status detail, not every section. Do not layer decorative shadows. Sticky elements must not cover headings or focus targets; offset anchor scroll accordingly.

# Shapes

Controls use `--radius-md`, cards use `--radius-lg`, compact fields and inner elements may use `--radius-sm`; chips, badges, progress tracks and status pills use `--radius-pill`. Shape and spacing are consistent across modes.

# Components

`theme.css` supplies the shared classes below. Mode CSS may compose them and add layout-specific selectors, but must not redefine their semantic meaning. Existing script hooks and IDs remain intact; add shared classes alongside needed legacy hooks.

- **Page and header:** `.page-container` wraps content. `.app-header` contains a text brand, `.app-nav[role=tablist]` with the existing `button.tab` and IDs `tab-day1`, `tab-after`, `tab-compare`, `tab-ops`, `tab-domain`, and one `.status-pill`. Tabs use `.on` and `aria-selected`; inactive tabs are neutral, active tab uses accent-soft and accent border/text. `.status-pill` is a keyboard-focusable summary with text and a compact aggregate indicator; reveal the three named service details on hover and `:focus-within`/focus. Keep actual `#dotLaya`, `#dotDecider`, `#dotStudio` nodes and their JS-updated classes, titles and accessible labels in those details. Aggregate from those existing states: down if any down, otherwise busy if any busy, otherwise up if all up, otherwise unknown. Indicate state in text, not just color. No new health request.
- **Intro:** `.page-head` contains an eyebrow, one h1 title and lead paragraph. Preserve `#heroTitle`, `#heroLead`, `#heroLine` and `#ctaHeroSlot` and mode-specific show/hide behavior.
- **Section:** `.section` contains `.section-head`, with eyebrow, heading, optional description and optional actions. Keep semantic heading order; omitted optional parts leave no empty space.
- **Card:** `.card` is a bordered surface with radius/padding above; `.card--muted`, `.card--success`, `.card--warning`, `.card--danger` use their matching soft surface with a visible semantic border and readable text. Do not imply a wrong answer from an untrained baseline alone.
- **Buttons:** `.btn` is an inline-flex, centered, font-inheriting control with 40px minimum height, 8px radius and 16px horizontal padding. `.btn--primary` is accent/white, `.btn--secondary` surface/text/border, `.btn--ghost` transparent/text with visible hover, `.btn--success` success/white, `.btn--sm` minimum 32px with 8px inline padding. `.btn[disabled]` and `.btn:disabled` use subdued colors, `cursor:not-allowed`, no hover affordance, but retain readable label. Text labels stay visible; no reliance on color for selection.
- **Chips and badge:** `.chip` is a compact inline-flex pill with a border and text label; `.chip--selected` uses accent-soft/accent and communicates selection via `aria-pressed` or the existing radio semantics. `.chip--success`, `.chip--warning`, `.chip--danger`, `.chip--info` use corresponding semantic soft backgrounds and dark foregrounds. `.badge` is a noninteractive compact pill for named state; selection remains a control, not a badge.
- **Stat:** `.stat` groups `.stat__value`, `.stat__label` and optional `.stat__delta` in that order; tabular value, readable label, and explicit before/after or unit in delta. Place in cards where appropriate, without losing denominator or caveat.
- **Data table:** `.table-wrap` contains a real `.table`, full-width, collapsed borders, 8px 12px cell padding, left-aligned headers and 1px row separators; no zebra stripes. `.table--sticky` on the table gives `thead th` sticky `top:0` within the scrolling wrapper, with opaque surface and z-index. `.is-changed` uses success-soft for after changes or warning-soft for before/new-rule context as specified by mode, plus a textual change annotation; `.is-wrong` uses danger-soft and ✗/text; `.is-right` uses success-soft and ✓/text. The row state never replaces the actual value.
- **Callout:** `.callout` is a bordered, padded surface; `.callout--info`, `.callout--success`, `.callout--warning`, `.callout--danger` use matching soft background and semantic text/border. Include heading/text and optional existing action; never use tint alone to identify state.
- **Disclosure:** `details.disclosure` contains a keyboard-operable `summary` and content, with border, surface, 8px radius, 12px padding and a visible open/closed indicator. Preserve nested disclosures and their copy.
- **Form controls:** label each input/select/textarea/range; use inherited font, surface, text, border, 8px radius and 8px padding. Inputs and selects have minimum 40px height, textarea width 100% and resizable vertically. Range uses accent and retains current displayed numeric value. Disabled controls and explanatory text remain visible; error copy sits adjacent to its control.
- **Segmented control:** `.segmented` groups related buttons with 4px gap; selection uses `.chip--selected` or button state and explicit `aria-pressed`/existing tab semantics. Keep keyboard-operable individual controls; do not change actions.
- **Progress:** `.progress` is a labeled track (`height:8px`, muted background, pill radius) containing `.progress__bar` with accent fill and width reflecting the existing value; provide accessible name and value where determinable, and never fake progress.
- **Loading and empty:** `.skeleton` is a muted rounded placeholder, paired with existing meaningful loading text/status; it must not replace error or progress text. `.empty-state` is a neutral compact region with the existing explanation and existing action if available.
- **Toast/status line:** `.status-line` is inline, text-first feedback beside the relevant action, with `role=status`/polite announcement as appropriate; `.toast` uses the same semantic presentation for existing transient feedback only. Do not invent notifications or convert blocking token prompts/confirmation into a new flow.
- **Focus and motion:** `:focus-visible` uses a 3px `--color-accent` outline with 3px offset on all interactive elements; never remove it without an equally visible replacement. Under `prefers-reduced-motion: reduce`, disable decorative animation and transitions and use instant scrolling, while retaining all state text and results.

# Do's and Don'ts

- Do maintain existing component hooks, exact dynamic content and caveats, including evidence, version/footer and local inference language.
- Do retain same-claim comparison, presenter-only controls, numeric denominators, and text/symbol alternatives to color.
- Do keep keyboard, touch, readable contrast and contained mobile table scrolling in every mode.
- Don't use decorative emoji, external assets, gradients as decoration, zebra striping or gratuitous elevation.
- Don't suggest historical claim training happens live, imply 100% is a deployment guarantee, equate held dollars with savings, or use color to hide a real miss.
