# Domain Builder v3 — "Change the rulebook, watch the model change" (plan)

Status: shipped 2026-10-28 (DEVELOPMENT_LOG Phase 10). Replaced the v2 teach table (`?mode=domain`).
Measured outcome: every changed decision learned on all 500 test rows for all nine presets, one
pass, 51–64 s click to result live.

## 1. What the audience sees today, and why it does not land

Walk the v2 page as a buyer (head of support / ops / HR, CIO, a sales engineer's prospect):

| Screen | What they see | What they think |
|---|---|---|
| Domain pick | three cards | fine |
| Opening | four percentages for four engines they have never heard of (Laya zero-shot, decider-4b, "decider after insurance training", rules), Wilson CIs, caveats | "which one is yours? why are they all bad?" |
| "Watch them struggle" | three truncated tickets with `routing=… · abuse review=…` against `gold: …` | wall of text; no picture of a mistake |
| "Now teach it" | a 12 × 7 grid of chips, "bulk-accept the rule gold, optionally edit one decision" | "what is gold? why would I click a cell?" — nobody knows what to change or why |
| Teach (90 s) | a progress bar with epoch/step | dead air |
| Result | "0% → 47%" all-7 on 30 held-out cases, a ✓/✗ table of hand-reworded probes, a drift button | the model is still wrong half the time; the "after" model is not visibly *different*, only less bad; nothing to try |

Root causes:
1. **No story.** The edit-a-cell mechanic has no business reason; nobody in the room owns the change.
2. **The before/after compares the wrong things.** "Before" is an untrained model, so *everything* differs and
   the taught change drowns in noise. A buyer wants to see *one rule change → exactly that behavior changes*.
3. **Nothing to touch afterwards.** There is no way to hand a ticket to the model and see the old and new
   behavior side by side, so the change is asserted by a number, not experienced.
4. **Jargon first, payoff last.** gold, zero-shot, epoch, rule profile, all-7.

## 2. How a product sales team would run this demo

Demo-craft rules the redesign follows:
- **Situation → change → proof → hands-on.** Every business runs on a rulebook that changes. The pain is
  how long a rule change takes to reach the system that makes decisions.
- **One "aha", rehearsed:** the audience picks a policy change, and within ~1½ minutes the model applies it
  to tickets it has never seen — visible flips, nothing else moves.
- **Before = today's production model, after = the same model re-taught.** Then the diff *is* the policy.
- **Audience participation:** the room chooses the change (and its values); anyone can then edit a ticket
  on their phone and watch old vs new model answer — the moment people believe it is real.
- **Trust signals:** a rulebook referee column (the rule's answer, with its evidence), unaffected decisions
  shown as unchanged, measured numbers, the honest limits in a fine-print panel at the end.
- **Plain words:** "your model", "the new rule", "tickets it never saw", "decisions that changed".
- **Facilitation, not invented claims:** during the 90 s, ask the room how long their last rule change took
  to reach production (no unmeasured "weeks" statistic on screen).

## 3. The scenario (5 acts, ~6 minutes)

1. **Meet the desk (45 s).** One real ticket, its 7 decisions in a decision card:
   out-of-the-box AI (Laya zero-shot) vs **your model** (Laya trained once on this desk's rulebook) vs the
   rulebook. Two big numbers over the sealed 500: out of the box `x/500` tickets fully right → your model
   `y/500`. *"This is your production model. Now the business changes."*
2. **Change the rulebook (60 s).** Three policy memos, each a plain sentence with editable values:
   - 🔀 *Escalate a whole queue* — "[Account] tickets that are not flagged go to [trust & safety]" (routing)
   - ⭐ *VIP fast lane* — "[Premium]-tier tickets are always at least [urgent]" (urgency)
   - 🛡 *Zero tolerance* — "Flag for review when at least [1] warning sign appears (was 2)" (four decisions)

   Picking one shows the impact live (CPU, instant): how many training/test tickets it changes, which
   decisions, three examples old → new, and the exam — 12 unseen tickets the rule changes + 12 it does not,
   with today's model's answers (it follows the *old* rule).
3. **Teach (≈90 s).** Presenter-only button. Phases on screen (prepare → learn → exam), elapsed timer,
   the exam grid waiting, and the facilitation prompt.
4. **See the difference.** The exam grid flips: on the tickets the rule changes, today's model is wrong by
   design and the re-taught model follows the new rule; on the others, nothing changed. Headline:
   "changed decisions now right: a/b (before 0/b) · kept decisions unchanged: c/d".
   A decision diff lists each changed decision before → after with the rule's answer.
5. **Try to break it.** Any ticket (exam tiles click into it) in an editable box, one-click mutators
   ("make it Premium", "remove the evidence", "big amount", "fresh account", "switch category"), and
   **Ask both models**: today's model | re-taught model | rulebook (with evidence), changed rows
   highlighted, latency shown. Open to everyone (read-only GPU inference, rate-limited); the rulebook
   column says "can't parse this wording" on free rewrites — the rules-engine brittleness, live.
6. **Fine print (collapsed).** Training config and timing, measured offline numbers on all 500, the
   paraphrase caveat, calibration caveat, the run log name.

## 4. Engineering

- **Policy = spec edit.** `domain_factory`: `flag_markers` (default 2) and `urgency.tier_floor` knobs
  (defaults keep corpora byte-identical — verified), routing by best category → unit (two categories may
  share a desk), `apply_policy` (spec copy + the rule sentence appended to the affected questions'
  instructions), `rule_gold`, `policy_training_rows` (300 changed + 300 unchanged corpus rows relabeled by
  the rules engine), `policy_exam` (first 12 changed + 12 unchanged holdout rows).
  Presets per domain in `domains.py` (`policies`, `noun_plural`).
- **Production checkpoints:** `studio-runs/<domain>/prod-ckpt`, Laya fine-tuned once on the domain's
  2,000 training rows (3 epochs). Re-teach starts from it (`--base prod-ckpt`), so the rest of the rulebook
  is kept and only the delta is learned.
- **Studio API (replaces session/train-with-edits/predict/drift):**
  - `POST /studio/session {domain}` → rulebook, presets + allowed values, baseline numbers (portfolio
    zero-shot summary + production answers on the holdout, cached on disk), showcase ticket, last taught
    policy.
  - `POST /studio/impact {domain, policy}` → CPU only: changed counts per decision, examples, exam rows
    with production answers.
  - `POST /studio/train {domain, policy}` (token) → re-teach from prod-ckpt; result = exam rows with
    before/after answers + summary + timing + config.
  - `POST /studio/compare {domain, state}` → production model (current rulebook) and taught model (its
    policy's rulebook) answers + both rulebook answers with evidence; public, one at a time, 409 while
    training.
  - The zero-shot Router leaves the studio (its holdout answers come from the portfolio file) — less VRAM,
    nothing to unload/restore around a teach.
- **Measured before shipping** (`measure_policy_teach.py`): per domain × preset, changed-decision accuracy
  before/after, kept-decision accuracy, all-7, train time — full 500 holdout and the 24-row exam.

## 5. Acceptance

- A first-time viewer can say, after the demo, what changed and why it matters (rule → model in ~1½ min).
- After a teach, the exam shows the changed decisions flipped to the new rule and unchanged ones kept,
  with numbers matching the offline measurement range.
- Anyone can edit a ticket and see the two models disagree exactly where the rule changed.
- Click-to-result under 2 minutes; no regression of the live stack (VRAM preflight, token gate, 409s).
