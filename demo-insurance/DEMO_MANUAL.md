# Demo operator & presenter manual — Insurance Claims Decision Console

Session development record (including operator Q&A and the failure ledger): `DEVELOPMENT_LOG.md`.
Run from the repo's `demo-insurance/` directory. · Console: **http://127.0.0.1:8901**
Runs on one machine with a CUDA GPU (~10 GB VRAM with all engines resident; author measurements used an RTX 5090 — see docs/ for provenance).

## 1. Running the demo — dev, live, and supervision

**Portable (repo tree, any machine):**

```bash
bash start_demo.sh            # laya :8901, decider :8902, studio :8903 (skips ones already up)
bash start_demo.sh --tunnel   # + cloudflared quick tunnel; public URL printed and saved to tunnel-url.txt
bash stop_demo.sh             # prints what it would stop — plan only, kills nothing
bash stop_demo.sh --yes       # stops all of the above + the studio's train_cli child (PID-attributed)
```

Venvs auto-detect from `../.venv-laya` / `../.venv-decider` (run `../setup.sh` once); override
with `LAYA_PY` / `DECIDER_PY` / `STUDIO_PY` (absolute python paths) and `LAYA_PORT` /
`DECIDER_PORT` / `STUDIO_PORT`. On the live machine the interpreters live inside the distrobox
`ai-dev`: `BOX=ai-dev LAYA_PY=/opt/ai-tools/venv-laya/bin/python DECIDER_PY=/opt/ai-tools/venv-decider/bin/python`.

- **laya service** `:8901` — serves the console AND both Laya engines: zero-shot Router
  (auto language routing) + fine-tuned English + fine-tuned multilingual checkpoints.
  Also proxies `/dec/*` and `/studio/*` — one public origin.
- **decider service** `:8902` — decider-4b v2.1, always untrained (that is the point of Engine C).
- **studio service** `:8903` — the Domain Builder: rule-change impact, re-teach, side-by-side
  compare, status. The re-teach route needs the token in `studio-token.txt` (auto-generated with a
  random secret on first start, chmod 600, never echoed); the presenter types it once in the
  console. It also needs each business's production model, `studio-runs/<domain>/prod-ckpt`
  (`train_prod_ckpt.sh`, ~7 min per business; stop the studio while it trains).

**Supervised (live machine):** the same services run as systemd `--user` units
`decision-demo-{laya,decider,studio,tunnel}.service`, grouped by `decision-demo.target`
(`deploy/systemd/`; failed services restart after 5 s). One-time setup:

```bash
demo-insurance/sync_live.sh               # repo -> live tree (see below)
demo-insurance/deploy/install_units.sh    # copies units + env file; prints start commands, starts nothing
systemctl --user start decision-demo.target            # the three services
systemctl --user start decision-demo-tunnel.service    # optional public URL -> tunnel-url.txt
```

Machine parameters (demo dir, distrobox name, python paths, ports, cloudflared binary) live in
`deploy/demo.env` — copy `deploy/demo.env.example` and edit; `install_units.sh` installs it as
`~/.config/systemd/user/decision-demo.env`. The studio unit refuses to start without
`studio-token.txt`. Note: the token reaches the studio through the environment, so any local user
can read it from `ps` — acceptable on a single-user demo box; the tunnel link is the real gate.

**Deploying a change:** edit in the repo, then `sync_live.sh` from `demo-insurance/`. It rsyncs
the repo tree to the live tree (`--checksum --delete`), keeps checkpoints, `studio-runs/`, logs,
tokens and caches intact, syncs `../docs/LAYA_DECIDER_EXPERIMENT_REPORT.md` into
`<target>/../docs/` (that is what `/report` serves), and writes the repo HEAD (plus `-dirty` when
the tree is dirty) to `VERSION` — shown by `/stats` and the footer. `--dry-run` lists pending
changes and exits non-zero while anything differs. Restart to load new code:
`systemctl --user restart decision-demo-laya decision-demo-decider decision-demo-studio`
(the tunnel and its URL keep running).

**Logs:**
- supervised services: `journalctl --user -u decision-demo-laya` (also `-decider`, `-studio`, `-tunnel`)
- start_demo.sh runs: `laya-service.log`, `decider-service.log`, `studio-service.log`, `cloudflared.log`
- studio training: `studio-runs/<domain>/train-<YYYYmmdd-HHMMSS>.log` — the full train_cli output;
  `/studio/status` shows parsed progress only, so go to the log when a teach fails.

Health dots in the top bar; `?mode=` URLs are shareable (`day1`, `after`, `compare`, `ops`, `domain`).
First request after a cold start takes ~1–2 s (CUDA warm-up); afterwards 10–30 ms per decision.

### Pre-show checklist

1. Units green: `systemctl --user status decision-demo.target` — laya, decider, studio `active (running)` (tunnel too, if used).
2. Health ok: `curl -s :8901/health`, `:8901/dec/health`, `:8901/studio/health` all report ok.
3. GPU room to teach: `/studio/health` free GiB ≥ its `teach_min_free_gib`, `warm` true and
   `prod_ready` true for every business; `pgrep -af laya.train_cli` finds nothing.
4. One phone test on mobile data through the tunnel URL — page loads, one preset answers.
5. `?mode=domain&d=support_tickets` renders all five steps; picking a rule shows its impact and the
   24-case exam; *Ask the models* answers with three columns (out of the box, your model, re-taught).
6. Wrong-token test: Re-teach with a garbage token is rejected and re-prompts; the real token works.
7. `VERSION` in the live tree equals the repo HEAD you meant to ship.
8. Disk and logs sane: `df -h .`, `du -sh studio-runs`, journal not ballooning.
9. Domain Builder starts fresh: on `?mode=domain` every card's badge reads "fresh — your model only".
   If not, press **↺ Reset every business to a fresh start** (token) — or
   `curl -X POST localhost:8903/studio/reset -H "X-Studio-Token: $(cat studio-token.txt)" -d '{"domain":"all"}'`.
10. After any restart, run one warm-up predict — first answer is the slow CUDA one (~1–2 s).

## 2. Sharing online (cloudflared)

```bash
cloudflared tunnel --url http://localhost:8901 > cloudflared.log 2>&1 &   # install: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' cloudflared.log | head -1
```

The printed `https://…trycloudflare.com` URL is the public demo link (no account needed; URL is
ephemeral — regenerate per session; a named Cloudflare tunnel can make it stable). The console,
both Laya engines and the decider proxy all flow through that one origin.

**Exposure notes (read before sharing widely):** no authentication on the demo; anyone with the
link can run inferences on your GPU. Inputs are not logged by the services; cloudflared and your
network see traffic metadata. Fine for a session with known recipients; revoke with `stop_demo.sh`.

## 3. What to show — the 8-minute arc

1. **Frame (1 min):** "Every claim triggers three small decisions — which unit, fraud or not, how
   urgent. Today people make them; a decision model makes them in milliseconds and shows you the
   probability it is acting on."
2. **Day 1 (3 min):** open `?mode=day1`. Run 2 standard presets — out-of-box Laya misses some.
   Then run a **FRAUD** preset: Laya says YES/NO with high confidence on the wrong side.
   decider-4b is right — "the bigger generalist is decent with zero data; the small one is lost."
3. **The reveal (1 min):** press the green **"⚡ Train on 12,000 past claims"** button — same claim,
   trained engine, all seven decisions correct with sharp probabilities. "Fifteen minutes of
   training on this machine, before the session. Nothing you are watching is recorded or staged."
4. **Multilingual (1 min):** compare mode, run 🇰🇷 Korean / 🇯🇵 Japanese presets — the zero-shot
   engine auto-routes to its multilingual checkpoint; the trained engine now also switches
   checkpoints per language (badge: `trained checkpoint: multilingual-finetuned`).
5. **Audience drives (2 min):** hand over the free-text box — paste any claim; discuss the
   probability bars. Scoreboard tallies preset hits per engine; Reset clears.

### The ops floor (the executive close) — `?mode=ops`

6. **Flip to ops (3–4 min):** "One claim is a toy; here is the operation." The sealed 500-claim
   holdout, all engines, measured once before the session. Every claim gets one disposition:
   **auto-paid** (straight through, no person), **flagged → SIU** (p(fraud) ≥ τ, held for the
   fraud unit) or **adjuster review** (not covered, or more than one touch expected).
   - **Read the six cards** (Laya fine-tuned, τ 0.80): 69.2% straight-through (346 claims), the
     engine's 7 decisions all right on 346/346 of them, 0 fraud paid out, $1,205,920 held for the
     SIU with 0 legit customers false-flagged, 68 claims left for adjusters.
   - **Honest beat:** this engine is *certain* on every claim (fraud probabilities exactly 0 or 1),
     so τ changes nothing — the note under the slider says so.
   - **The risk dial:** switch the engine to **decider-4b zero-shot** and hand the slider to the
     audience. τ 0.95: 62.8% straight-through, 9 frauds paid out ($205,500), 63 legit customers
     false-flagged. τ 0.50: 57.4%, 8 frauds, 106 false flags. Throughput vs leakage vs customer
     friction — that is the buy/no-buy conversation.
   - **Human in the loop:** back on Laya fine-tuned. *Flagged → SIU* view: press **Auto-pay** on a
     fraud claim — the "fraud paid out" card turns red and the held $ drop by that amount. *Adjuster
     review* view: **Flag fraud** on a legit claim — a false flag appears; **Auto-pay** on another —
     straight-through ticks up, adjuster workload down. *Auto-paid* view: **To adjuster** pulls a
     claim back for a spot-check. Overridden rows stay put, shaded, with "↺ engine said …";
     **Reset overrides** restores the measured state.
   - The calibration strip shows, per probability bin, the share of claims that were actually
     fraud. Engine D (rules) is perfect on the phrasing it was built for and answers `unparsed` to
     all seven questions on the Korean claim — that is the incumbent's real shape.

### The Domain Builder (the closer) — `?mode=domain`

The story: *every business runs on a rulebook that changes; a decision model is only useful if
it keeps up.* Five steps on screen (sticky step bar at the top), about six minutes. Deep link a
business with `?mode=domain&d=support_tickets` (or `logistics_exceptions`, `hr_exceptions`).

7. **Your model today (45 s).** Pick a business. Two numbers: out-of-the-box Laya gets 5 of 500
   support tickets fully right (0 logistics, 10 HR); the same Laya trained once on 2,000 past
   cases gets 487 (498, 493). Under it, one ticket and its seven decisions — out of the box ✗,
   your model ✓, the rulebook. *"This is your production model. Now the business changes."*
8. **Change a rule (60 s).** Let the room pick one of three memos; every value is a dropdown:
   - 🔀 *Escalate a whole queue* — "[account] tickets go to [trust and safety]" (one decision)
   - ⭐ *VIP fast lane* — "[Premium]-tier tickets are always at least [urgent]" (one decision)
   - 🛡 *Zero tolerance* — "Flag for review at [1] warning sign(s)" (four decisions move)

   The impact appears instantly: how many of the 500 test cases the rule changes, which
   decisions, and the exam — 24 cases the model never saw, 12 the rule changes (amber: today's
   model still follows the old rule) and 12 it doesn't. Setting a value back to today's rule
   disables Re-teach ("that is today's rule").
9. **Re-teach (≈1 min).** Press ⚡ Re-teach (token once per browser session). Phases: prepare →
   learn (loading your model, then the pass) → exam, with a clock. Use the minute: *ask the room
   how long their last rule change took to reach the system that decides, and who had to be
   involved* — that answer is the business case; no number is claimed on screen.
10. **What changed.** The exam flips with an animation: "On the 12 unseen tickets the new rule
    changes, your model now follows it on 12 (before: 0). On the 12 it leaves alone, 12 are
    still fully right." Three tiles: changed decisions right before → after, untouched decisions
    still right, cases fully right under the new rulebook. A red tile is a real miss — read it out.
11. **Try to break it (2 min).** Click any exam tile (or edit the text box). **Ask the models**:
    Laya out of the box (no training), your model, the re-taught model and the rulebook side by
    side, with a score chip per model. Your model and the re-taught one *should* match on cases
    the rule doesn't touch — the training difference is the out-of-the-box column. The changed decision is
    highlighted, latency in ms. One-click edits flip the rule on purpose — the button matching
    the taught rule is highlighted (make it Premium / remove the evidence / make it a conduct
    case). ✍️ *Reword it* loads a hand-written rewording: the rulebook can't read it, so the
    console stops refereeing and says so — the incumbent's real weakness; the models still
    answer. Anyone on the public URL can do this step from a phone (read-only inference).

Studio notes for the operator: runs as `decision-demo-studio` (systemd user unit; localhost
:8903, proxied through :8901). Re-teach needs the token — anonymous visitors follow a running
re-teach live (their page switches to the rule being taught and shows the result) but cannot start
one; while it runs, compare answers "the model is being re-taught". One job at a time. Before
training the studio unloads its two engines, then refuses to start below `TEACH_MIN_FREE_GIB`
(11.5) free — a plain "not enough GPU memory" message instead of a crash. Each re-teach starts
from `prod-ckpt` (never cumulative) and replaces `ft-ckpt` only on success; its result persists
in `last-result.json`, so a reload or a latecomer sees the last run. Every page says which model is
active — a green "Fresh start" bar or an amber "A re-taught model is active — “rule” (finished …)"
bar, plus a badge on each business card. The amber bar's **↺ Reset to a fresh start** button
(token) deletes the re-taught model for that business; the production model is never modified,
so there is nothing else to reset. Open pages, including the audience's, switch to the fresh state
within ~2 s. Reset is refused (409) while a re-teach runs.

| measured with the full live stack serving | value |
|---|---|
| click → result (browser via the tunnel, phone layout, API) | **51–64 s** (support VIP 64 s; logistics zero tolerance 52 s; HR escalate 51 s; support zero tolerance 51 s; support escalate 51 s) |
| exam: decisions the rule changed, right | every one in every live run — 12/12 (VIP, escalate), 41/41 and 45/45 (zero tolerance); before: 0 |
| exam: untouched decisions, right | 155/156 (support VIP) and full marks in the other four runs |
| all 500 test cases, per preset (offline, one pass) | changed decisions 88/88 … 899/899; untouched 99.1–99.9% |
| GPU peak (whole card) / `/predict` during a re-teach | 27.6 GiB / 70 of 70 requests OK |

Knobs (env file `~/.config/systemd/user/decision-demo.env`): `TEACH_EPOCHS` (1),
`TEACH_CHANGED_ROWS` (300), `TEACH_SAME_ROWS` (300), `TEACH_MICRO_BATCH` (8), `TEACH_GRAD_ACCUM`
(2). A second pass measured no better (DEVELOPMENT_LOG Phase 10). Every run's full log:
`studio-runs/<domain>/train-<timestamp>.log`.

## 4. Numbers you may quote (measured on 500 unseen claims, 7 questions each, this machine)

| Engine | accuracy | All-seven-correct rows |
|---|---:|---:|
| Laya out-of-box | 46.4% | 1/500 |
| decider-4b (no training) | 70.8% | 21/500 |
| **Laya fine-tuned (12k claims)** | **100.0%** | **500/500** |
| **decider-4b + LoRA (same 12k)** | **100.0%** | **500/500** |
| Rules engine (Engine D) | 100.0% *English phrasing only* | 500/500 — `unparsed` on non-English |

(An earlier run quoted 99.9%/497: a comparator bug — laya emits near-integer score floats like
1.0001 — not a model error; see DEVELOPMENT_LOG ledger #10.)

**Decider-4b after insurance training, scored on new domains it never trained on:**
support tickets 81.4% · logistics exceptions 93.3% · HR exceptions 89.9% avg per decision
(all seven correct: 176/500 · 335/500 · 261/500; zero-shot base 60.7% / 69.7% / 70.9%; laya
zero-shot 53.5% / 40.7% / 58.4%). Read it as format + journey transfer: the gains concentrate on
questions whose answer vocabulary is shared across domains (touches, money bands, the flag);
routing to domain-specific teams moves least. Insurance training cannot teach `billing_desk`.

**The parity result (what fine-tuning does to the decider):** the same 12,000 rows that took
Laya from 46.4% to 100.0% took decider-4b from 70.8% to **100.0%** (LoRA rank 64, 2 epochs,
71 minutes, merged to bf16) — and it **kept its languages**: 140/140 preset questions including
Korean, Japanese, Hindi and Spanish. Caveats, stated plainly: train and holdout come from the
same templated generator (in-distribution); post-training confidences hit the calibration floor
(razor-sharp — treat thresholds as uncalibrated until recalibrated on real data); no
general-benchmark regression was re-run on the merged weights.

Ops floor (τ = 0.80, fine-tuned Laya as the working engine): 69.2% straight-through (346
claims, $2,263,860), every auto-paid claim correct on all seven decisions (346/346; Wilson
95% CI 98.9–100%), 0 fraud claims paid out, $1,205,920 held for the SIU (86 flagged) with $0
false-flagged, 68 claims ($531,470) on adjusters' desks. The fine-tuned engine's fraud
probabilities are exactly 0/1, so τ does not move these numbers; the year projection on screen
is illustrative at the synthetic mix (17.2% fraud) and counts dollars held for investigation,
not money saved.

v1 comparison (3-question era, same corpus seed): 37.8% / 100.0% / 74.1%. Study context: on the
prior sealed corpus Laya-ft beat the adapted 8B CLM model on every endpoint
(`LAYA_DECIDER_EXPERIMENT_REPORT.md`).

## 5. Language handling (measured, and why Engine B is English-only)

The English fine-tuned checkpoint **trades away language robustness**: on a Spanish claim it
scored 1/3 where the untrained base scored 2/3 — fine-tuning to zero loss on templated English
narrows the model (catastrophic forgetting of anything off-distribution). A second checkpoint
fine-tuned from the multilingual base on the same English data gave mixed cross-lingual results
(Korean/Japanese improved, Hindi regressed; 8/9 vs 7/9 on the four multilingual presets). Per
operator decision, the demo therefore shows the **English fine-tune only**; non-English claims
get an explicit note and Engine A's zero-shot multilingual checkpoint answers them. To build a
proper multilingual fine-tune you need multilingual training rows (translated or per-language
synthetic data), not English-only data.


## 6. Q&A cheatsheet

- *"Is the fine-tuned model always right?"* — On this claim family it maxed the exam; the planning
  number is always the unseen-distribution figure (92% on the study corpus). Never quote 100% as
  a deployment promise.
- *"Why does trained Laya show 100% confidence?"* — Its yes/no calibration is uncalibrated after
  fine-tuning (training warning retained); show probabilities, recalibrate before real thresholds.
- *"Does it write answers?"* — No. Options in, probabilities out; a wrong format is impossible.
- *"Who acts?"* — Nobody. Thresholds route: ≥0.9 auto, 0.6–0.9 review, below escalate; people keep
  authority (same recommend–authorize–execute pattern as the study decks).
- *"Where does training data come from?"* — 12,000 synthetic past claims with rule-computed answers
  (`gen_corpus.py`); in production this would be your historical labeled claims.
- *"Did the re-taught model just memorize the exam?"* — No: the exam cases are sealed test rows it
  never trained on; it learned from past cases the rulebook re-decided under the new rule. Then hand
  it your own wording in step 5.
- *"Can we change several rules at once?"* — Each re-teach starts from the production model and
  teaches one rule; combined changes have not been measured yet — say so.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Top-bar dot red | service down → `start_demo.sh`; check `*-service.log` |
| First answer slow | CUDA warm-up; second run is milliseconds |
| Multilingual preset shows note instead of answers | multilingual fine-tuned checkpoint missing → it fell back; retrain with `laya.train_cli --base <laya snapshot>/multilingual` |
| Tunnel URL dead | quick tunnels are ephemeral → restart cloudflared, share the new URL |
| GPU busy / other ML work running | stop_demo.sh first; engines need ~10 GB VRAM |
