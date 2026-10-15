# Plan — demo review fixes (2026-10-15)

Source: five independent reviews (buyer, UX, claims audit, live ops, security) of the live
console, top findings re-verified against code and data. Order = the agreed priority:
**P0 Teach reliability → P1 correctness → P2 honesty → P3 presentation → P4 operations.**
Each item lists files, the change, and the check that proves it.

---

## 0. Diagnosis — "training failed: train_cli exit 1" (live, 22:44:17)

**Cause: CUDA out-of-memory 7 s into the first optimizer steps.** Evidence (public
`/studio/status`, the only place the output was kept):

```
train items 11780, calibration items 400, skipped {}, device cuda
[W1015 22:44:24 CUDACachingAllocator.cpp:528] expandable_segments: memory mapping failed with OOM
  on device 0 while trying to map 20971520 bytes (free: 14417920, total: 33743044608)
…iB memory in use. Including non-PyTorch memory, this process has 8.49 GiB memory in use.
  Of the allocated memory 7.78 GiB is allocated by PyTorch …
error: train_cli exit 1
```

Memory budget (nvidia-smi at 22:49, nothing training):

| process | GPU MiB |
|---|---|
| decider_service.py :8902 | 9,074 |
| laya_service.py :8901 (restarted 17:36) | 7,868 |
| studio_service.py :8903 (up since 16:16) | 5,318 |
| zed editor | 360 |
| **used / total** | **23,322 / 32,607** |

The teach subprocess needs ≈10.3 GiB (Phase 7 measurement: 21.8 GiB stack → 32.1 GiB peak).
Free is ≈9.2 GiB, so the run cannot fit; at the moment of failure only 14 MB were free.
The headroom measured in Phase 7 was 0.5 GiB — any growth kills it. Growth since then:
studio 3–4 → 5.3 GiB, zed +0.36 GiB.

`[INFERENCE]` why studio grew: it never evicts (`_ft[domain]` kept resident,
`studio_service.py:180`), and every anonymous domain-card click runs a full zero-shot pass
over 500 rows (`/studio/session`), leaving allocator cache behind. Not provable from outside
the process — item 0.4 adds the instrumentation that will.

**Why it was hard to diagnose (logging gaps):**
- train_cli output is kept only in memory, truncated to the last 200 chars per line
  (`studio_service.py:172`). The OOM line lost its head ("Tried to allocate …"); nothing on disk.
- The error shown to the user is just `train_cli exit 1`; the OOM is not classified.
- `service-decider.log` logs no requests; there is no GPU-memory endpoint.

### P0 — make Teach reliable

| # | Change | Files | Verify |
|---|---|---|---|
| 0.1 | Write the full train_cli output to `studio-runs/<domain>/train-<ts>.log`; keep only parsed progress (`epoch 1/2 · step n/N`) in `_job`; classify failures (`out_of_gpu_memory` if the log contains `OOM`/`OutOfMemoryError`, else `train_failed`) with a plain message: "Not enough GPU memory free (X GiB of Y needed) — no audience traffic is lost; retry after …" | studio_service.py, index.html (status line) | Force an OOM (start teach while a dummy tensor holds VRAM); log file has the full traceback; UI shows the classified message |
| 0.2 | Pre-flight: `torch.cuda.mem_get_info()` before launch; refuse with 503 + the same message below `TEACH_MIN_FREE_GIB` (measured need + 1 GiB margin) | studio_service.py | Same forced-low-memory case returns 503 instantly, no subprocess |
| 0.3 | Free the studio's own memory before launch: drop `_ft` (`_ft.clear()`), move the zero-shot router to CPU during training, `gc.collect(); torch.cuda.empty_cache()`; reload after. Only one taught ckpt resident at any time | studio_service.py | nvidia-smi: studio process ≤ ~1 GiB while training |
| 0.4 | Lower training peak: measure `--micro-batch 1 --grad-accum 16` (same effective batch 16 as 2×8) and `--max-len` at the corpus p99 token length; adopt whichever keeps accuracy (taught 12-case and fresh-30 scores unchanged vs 2/8) at the lowest peak | studio_service.py | Peak VRAM recorded via `nvidia-smi --query-compute-apps` sampling; target ≥ 3 GiB headroom with full stack resident |
| 0.5 | Stop anonymous GPU work: cache `stratified_cases(domain)` (deterministic, Random(7)) at first call / startup and return deep copies; `/studio/session` and `/studio/drift` return 409 "teach in progress" while training; `/studio/drift` requires the token or serves a cached result | studio_service.py, index.html | 2nd card click returns in < 100 ms; 20 concurrent `/studio/session` calls during a teach don't change GPU usage |
| 0.6 | Fallback if 0.3–0.4 still leave < 3 GiB margin: decider "teach mode" — `/admin/offload` moves decider to CPU for the teach, Engine C card shows "paused while the studio trains", restored after | decider_service.py, studio_service.py, index.html | Teach succeeds with decider paused; decider answers again within 10 s after |
| 0.7 | Expose `/studio/health` → `{gpu_free_gib, gpu_used_gib, job, last_error_kind}`; topbar gets a studio dot (amber while training) | studio_service.py, laya_service.py proxy, index.html | Dot reflects state from every tab |
| 0.8 | Training-time truth: measure the post-0.4 duration; consider fewer background rows (1,500 → 600) if accuracy holds, aiming ≤ 5 min; button copy shows the measured number | studio_service.py, index.html | Before/after table in DEVELOPMENT_LOG |
| 0.9 | Crash safety: persist train PID to `studio-runs/<domain>/train.pid`, kill stale PIDs on studio start; UI treats `idle` after a started run as "training lost — studio restarted" and re-enables Teach | studio_service.py, index.html | Kill studio mid-teach → no orphan in nvidia-smi; UI recovers |

Acceptance for P0: a full live Teach on each of the 3 domains completes with the full live
stack serving, while a script hammers `/predict` and `/studio/session`; peak VRAM and
duration logged.

---

## P1 — on-screen correctness (each is S)

| # | Issue (verified) | Change | Verify |
|---|---|---|---|
| 1.1 | 14/16 English preset labels describe a different claim (labels are the *intended* force, only category+fraud are forced) | `gen_corpus.py`: build the label from the generated meta (`"motor · side-swiped in a parking garage · docs attached"`); fraud presets keep their reason; rng order untouched → train/val/holdout SHAs unchanged, presets file regenerated | CI corpus step: only `demo_presets.json` labels change; spot-check all 20 |
| 1.2 | "level 1.00 ✗ wrong" when gold is 1 — `verdictFor` (index.html:254), ops auto-correct check (:484), struggle-card filter (:660) use exact float equality | One `scoreEq(a,g)` helper rounding like `build_portfolio.correct()`, used at all three sites | First preset: touches ✓; top-bar score recomputed; struggle cards only show true errors |
| 1.3 | τ slider is inert (fine-tuned fraud p is exactly 0/1 on 500/500) and destroys itself (drawOps rewrites the slider's own container) | Render controls once, update only counters/table/calibration; drive τ with an engine that has graded probabilities (selector: zero / decider / fine-tuned) or annotate "fine-tuned engine is certain on every claim here — τ has no effect; see calibration caveat" | Drag slider on decider arm → STP and fraud-slipped move; drag is continuous |
| 1.4 | Domain edits never reach the 1,500 background rows (`meta_by_state` keyed on holdout states, 0 hits in all 3 domains); badge claims they propagate | Key profiles from the train rows' own meta (add `meta` to domain train rows or recompute via `domain_factory.parse_state`); unit-check: an edit on profile P relabels N>0 rows | Count of relabeled rows shown in the badge; taught model follows the edit on an *unseen* same-profile case |
| 1.5 | "after" headline scored on the 12 teach cases (trained ×20); "fresh 30" overlaps teach cases (0/1/2 per domain) | Headline = fresh sample excluding teach ids (and excluding edited profiles' original gold); teach-case score labeled "on the cases it was taught" | Overlap 0 asserted in code |
| 1.6 | Rules engine answers 5/7 questions confidently wrong on non-English claims | `rules_engine.py`: if the claim isn't parsed (no incident/amount/date), every question → `unparsed`; no cascade into band/touches | POST /rules on KO/JA/HI/ES presets → all `unparsed`; EN holdout still 500/500 |
| 1.7 | Calibration title "says 1%", caption calls fraud rate "accuracy", rows labeled `dec/dec_ft/zero/ft` | Title "Calibration — fraud flag", caption "share of claims in this bin that were actually fraud", full engine names | Visual check |
| 1.8 | UI dead-ends: Teach stays disabled after a network error; wrong token sticky in sessionStorage | Re-enable in catch; remove token on 403; prompt again | Wrong token → retry prompts |

---

## P2 — honesty pass (S–M)

- **2.1** Stat cards: name the metric ("avg per decision") and add the all-7 rate from
  `rows_all_correct` (zero 1/500, decider 21/500) and Wilson 95% CIs (500/500 → 99.2–100%).
- **2.2** In-template caveat wherever 100% appears: "train and test share one generator —
  reworded probes 0/3, shifted-phrasing study 92.0%".
- **2.3** Year projection → "Illustrative at this synthetic mix (17.2% fraud): N claims/yr
  straight through; $X/yr routed to review instead of auto-paid". Drop "held".
- **2.4** Cross-domain card → "decider-4b after insurance training (format + journey
  transfer)"; show all-7 rate (support 35.2%).
- **2.5** One source of truth for numbers: manual §4 ops paragraph, README tables (still v1
  37.8%), training times (10/15/30–40 min, button "~1–2 min"), footer ("decider untrained",
  studio recipe) regenerated from `stats.json` / measured values; footer links the experiment
  report (serve `docs/LAYA_DECIDER_EXPERIMENT_REPORT.md` at `/report`).
- **2.6** Rules engine scoreboard label "Rules engine (hand-coded policy)" plus a pinned
  non-English example in compare mode.

---

## P3 — presentation (M)

- **3.1** Hero: one outcome line from measured numbers + a call-to-action bar ("Run this
  console on 500 of your historical decisions"); domain-neutral page title in domain mode.
- **3.2** Shared-link default `?mode=ops`; narrated opener stays day1. Day1 hides the
  fine-tuned stat card until the reveal.
- **3.3** Compare mode: question × engine matrix (answer chip, ✓/✗, confidence; bars on
  demand, omitted ≥ 95%).
- **3.4** Decision above the fold: collapse "What we asked" (closed by default), preset list
  one line each (rule answers in a details/tooltip), capped height.
- **3.5** Loading / error states: per-engine "thinking…" skeletons; presets failure with retry;
  one dead service → one "unavailable" card (not a blank console).
- **3.6** Payloads: `/portfolio` and `/studio/portfolio` send summaries (cards, top queue rows,
  calibration bins), not 3.1 / 2.6 MB.
- **3.7** Teach table: read-only gold chips with click-to-edit, edited cells highlighted, full
  case text on hover; progress bar + elapsed/ETA; button labeled "presenter-only".
- **3.8** Plain-language pass: τ → "auto-approve cutoff", "via english" hidden, snake_case
  enums humanized, priority shown as integer.
- **3.9** Mobile + a11y: table scroll wrappers (fixes the 583 px overflow), tab roles +
  aria-selected + pushState history, domain cards as buttons, text labels on health dots,
  `lang` on non-English claims.

---

## P4 — operations & security (S–M)

- **4.1** One supervised launcher for laya, decider, studio (token from `studio-token.txt`,
  refuse to start without one) and cloudflared: systemd `--user` units with
  `Restart=on-failure`; delete divergent script copies.
- **4.2** `sync_live.sh`: rsync repo → live tree (excluding checkpoints, logs, tokens,
  studio-runs), writes git HEAD to `VERSION`, shown in `/stats` and footer.
- **4.3** Input hardening: 64 KB body cap (413), JSON parse inside try (400), state length
  cap, ignore client-supplied question lists beyond the served schema, bounded GPU semaphore
  per service.
- **4.4** `domain` parameter validated against the domain registry on GET routes
  (path traversal confirmed live).
- **4.5** `/studio/status` exposes parsed progress only; 5xx bodies generic, details in logs;
  `hmac.compare_digest` + attempt throttle on the token; CORS only for `null`/localhost origins.
- **4.6** Decider request logging with duration; fix "serving on 0.0.0.0" message.
- **4.7** Pre-show checklist in DEMO_MANUAL §1: all units green; `/health`, `/dec/health`,
  `/studio/health` ok; ≥ teach-need + 3 GiB free and no `train_cli` running; one phone test on
  mobile data; Domain card renders; wrong-token test; `VERSION` = repo HEAD; logs/disk sane;
  warm-up predict after any restart.

---

## Delivery

- Each phase: one commit, sync to the live tree via 4.2 (until then: `cp` + byte check), smoke
  through the tunnel in a headless browser counting **visible** elements, CI green.
- DEVELOPMENT_LOG: Phase 8 entry + failure-ledger rows for the teach OOM (#11), preset label
  mismatch (#12), dead relabel path (#13), float comparator regression in the UI (#14).
- Service restarts only for P0 (studio, possibly decider) and P4; seconds of downtime, tunnel
  untouched.
