---
title: 'Demo site revamp — one clean, professional look and feel across all five modes'
type: 'feature'
ticket: ''
created: '2026-10-28'
status: 'done'
baseline_revision: '8b119a48cf65ba054259e44c94b3e031c05036c3'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/ux-demo-site/DESIGN.md', '{project-root}/_bmad-output/ux-demo-site/EXPERIENCE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The demo console grew mode by mode (claim console, ops floor, Domain Builder). Each has its own card, button, chip and table styles, emoji-heavy headings, inline styles and uneven spacing, so the site looks like three prototypes stitched together rather than one product.

**Approach:** Same content, numbers and behaviour; one professional visual system and interaction language applied to every mode: a product header with integrated navigation and one status indicator, consistent section headers, cards, buttons, chips, tables, callouts, loading/empty/error states, typography and spacing, no decorative emoji. Split the 1,800-line single file into a markup shell plus per-mode CSS/JS assets so each mode can be restyled independently.

## Boundaries & Constraints

**Always:** every number, caveat, label meaning, flow and API call stays; `?mode=` and `?d=` URLs, element IDs used across scripts, tokens (studio token prompts), presenter-only gates and reset/re-teach behaviour unchanged; works at 1366 and 390 px with no page-level horizontal overflow; keyboard focus visible; reduced motion respected; amber = before/day 1, green = after/positive, red = wrong stay meaningful; no external fonts, CDNs or frameworks; ✓/✗ marks stay (functional).

**Never:** change services' APIs, data, measurements or studio/decider code; restart decider or studio or touch the tunnel; add dark mode or new features.

</frozen-after-approval>

## Code Map

- `demo-insurance/index.html` -- today: CSS 7-257 (shared, Domain Builder 105-197, claim console 198-257), shell markup 259-381, JS 383-1802 (core+console 383-864, ops 865-1046, Domain Builder 1047-1790, startup 1792-1801).
- `demo-insurance/laya_service.py:206-222` -- static routes; add a whitelisted `/assets/<name>.(css|js)` route.
- After split: `demo-insurance/index.html` (shell markup), `demo-insurance/assets/{theme,console,ops,domain}.css`, `demo-insurance/assets/{core,console,ops,domain,main}.js` (classic scripts, load order core → console → ops → domain → main).

## Tasks & Acceptance

**Execution:**
- [ ] Phase 1 (parallel): split into shell + assets with the route; whole-site UX spines `_bmad-output/ux-demo-site/{DESIGN,EXPERIENCE}.md` as the contract.
- [ ] Phase 2 (parallel, one owner per file set): shell+theme+core; claim console; ops floor; Domain Builder.
- [ ] Phase 3: staging verification, deploy with one laya restart, live smoke (claim reveal, ops override, domain impact + compare + one re-teach + reset), docs + screenshots + dev log, commit.

**Acceptance Criteria:**
- Given any mode, the header, navigation, section headers, buttons, cards, chips, tables and callouts look and behave the same way.
- Given the split, behaviour before restyling is identical to `8b119a4` (same flows, zero page errors).
- Given the restyle, every flow verified in Phase 11 and Phase 10 still works through the public URL; zero page errors at 1366 and 390 px.

## Implementation Notes

- Split `demo-insurance/index.html` into the markup shell, `assets/{theme,console,ops,domain}.css`
  and ordered classic scripts `assets/{core,console,ops,domain,main}.js`; the laya service
  serves whitelisted assets at `/assets/` with no-store.
- Applied the UX spines' shared design system across all modes, removing inline styles and
  decorative emoji in favor of consistent components, one header/status pill and one intro per mode.
- Two corrective rounds addressed duplicate ops/domain intros and the insurance hero on ops,
  hidden phone ops override buttons, claim-card highlight spacing and the repeated Day 1 holdout sentence.
- Verified staging and live via the public tunnel at 1366 and 390 px: all five modes, zero page
  errors or page-level horizontal overflow, claim reveal, ops override/reset and Domain Builder
  impact/compare. A live support desk VIP re-teach took 64 s, with 12/12 changed decisions and
  12/12 untouched cases fully right, then reset to fresh.
- Restarted the laya service in ~11 s; the tunnel was untouched.

## Plan Change Log

## Review Triage Log

## Verification

**Manual checks:** browser through the tunnel with request interception serving the repo's shell and assets (staging) before deploy; then live after deploy.
