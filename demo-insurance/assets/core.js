const ENGINES = {
  zero: {tag:"Engine A", name:"Laya — out of the box", sub:"421M · zero training"},
  ft:   {tag:"Engine B", name:"Laya — fine-tuned", sub:"421M · trained on 12,000 claims"},
  dec:  {tag:"Engine C", name:"decider-4b", sub:"4.2B · zero training, generalist"},
  rules:{tag:"Engine D", name:"Rules engine (hand-coded policy)", sub:"keyword + date parsing · the way automation is built today"},
};
const MODE_ENGINES = {day1:["zero","dec"], after:["ft","dec"], compare:["zero","ft","dec","rules"], ops:[], domain:[]};
const QTITLE = {routing:"Route to unit", fraud_review:"Flag for fraud investigation?", urgency:"Priority",
  coverage_eligibility:"Coverage eligibility", net_payable_band:"Net payable band",
  subrogation:"Pursue third party (subrogation)?", expected_touches:"Expected adjuster touches"};
const ARM_LABEL = {zero:"Laya zero-shot", ft:"Laya fine-tuned", dec:"decider-4b zero-shot",
  dec_ft:"decider-4b fine-tuned", rules:"Rules engine (hand-coded policy)"};
const OPS_ARMS = [["ft","Laya fine-tuned"],["dec_ft","decider-4b fine-tuned"],["dec","decider-4b zero-shot"],["zero","Laya zero-shot"]];
const CAVEAT_100 = "train and test share one generator — on hand-reworded cases the Domain Builder's production models get 0–3 of 3 fully right per business (57/63 decisions); shifted-phrasing study 92.0%";
const TEACH_ETA = "~1 min";   // Domain Builder re-teach, measured click-to-result 64–65 s (600 rows, 1 pass from the production model) with the live stack serving
let PRESETS = [], QUESTIONS = null, STAGES = [], MODE = "day1", LAST = null, LAST_RUN = null, RUN_ID = 0;
const DAY1_ANSWERS = new Map();
const STORY_RUNS = new Set();
let SHOW_DECISION_DETAILS = false;

const $ = (id) => document.getElementById(id);
const fmtP = (p) => (100*p).toFixed(1) + "%";
const esc = (s) => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const humanize = (s) => String(s).replace(/_/g," ").trim();
const usd = (n) => "$" + Math.round(n).toLocaleString("en-US");
const mmss = (s) => { s = Math.max(0, Math.round(s||0)); return Math.floor(s/60) + ":" + String(s%60).padStart(2,"0"); };
// Scores/touches gold is integer-valued; laya emits near-integer floats (1.0001). Same rounding
// as build_portfolio.correct().
const scoreEq = (a, g) => Math.round(a) === Math.round(g);
function wilson(k, n){
  if (!n) return null;
  const z = 1.96, p = k/n, d = 1 + z*z/n, c = p + z*z/(2*n),
        r = z*Math.sqrt(p*(1-p)/n + z*z/(4*n*n));
  return [100*Math.max(0,(c-r)/d), 100*Math.min(1,(c+r)/d)];
}
const fmtCI = (k, n) => { const ci = wilson(k, n);
  return ci ? `(${(100*k/n).toFixed(1)}%; Wilson 95% CI ${ci[0].toFixed(1)}–${ci[1].toFixed(1)}%)` : ""; };

// Same-origin when served over http (local :8901 or a cloudflared tunnel); decider is proxied
// through the laya service so one public origin serves everything. file:// falls back to localhost.
const SAME = location.protocol.startsWith("http");
const QP = new URLSearchParams(location.search);
const LAYA = SAME ? location.origin : (QP.get("laya") || "http://127.0.0.1:8901");
const DECBASE = SAME ? LAYA + "/dec" : (QP.get("dec") || "http://127.0.0.1:8902");
const DEC = DECBASE + "/predict";

const HERO = {
  insurance: {title:"One claim, side by side",
    lead:`Pick one claim and follow seven decisions from untrained engines to a model trained on past claims.`},
  ops: {title:$("era-ops").querySelector("h2").textContent,
    lead:$("era-ops").querySelector("p").textContent},
  domain: {title:"Change one rule, watch the model change",
    lead:`A decision model is only useful if it keeps up with the business. Pick a rule change, re-teach the model live on this GPU, and see exactly which decisions move — on cases it has never seen.`,
    secondLead:$("era-domain").querySelector("p").textContent},
};
function applyHero(kind){
  const h = HERO[kind] || HERO.insurance;
  $("heroTitle").textContent = h.title;
  $("heroLead").textContent = h.lead;
  $("heroSecondLead").textContent = h.secondLead || "";
  $("heroSecondLead").hidden = !h.secondLead;
  document.title = "Decision Console · " + (kind === "domain" ? "Domain builder" : kind === "ops" ? "Ops floor" : "Claim console");
  document.querySelector("footer").before($("ctabar"));
  $("ctabar").hidden = (kind === "domain" || kind === "compare");
  // The claim console's summary row carries these numbers; the sentence would repeat them (and spoil Day 1).
  $("heroLine").hidden = true;
}

function modeFromLocation(){
  const m = new URLSearchParams(location.search).get("mode");
  return ["day1","after","compare","ops","domain"].includes(m) ? m : "ops";
}

function setMode(m, keepClaim, push){
  MODE = m;
  document.querySelectorAll(".tab").forEach(t => {
    t.classList.toggle("on", t.dataset.mode === m);
    t.setAttribute("aria-selected", t.dataset.mode === m ? "true" : "false");
  });
  if (window.matchMedia("(max-width:760px)").matches){
    const tab = $("tab-"+m), bar = tab.parentElement;
    bar.scrollLeft = tab.offsetLeft - bar.offsetLeft;
  }
  for (const k of ["day1","after","compare","ops","domain"]) $("era-"+k).hidden = (k !== m || k === "ops" || k === "domain");
  const wide = (m === "ops" || m === "domain");
  $("opsfloor").hidden = (m !== "ops");
  $("domainfloor").hidden = (m !== "domain");
  $("mainStats").hidden = wide;
  $("claimGrid").hidden = wide;
  $("storyStrip").hidden = wide;
  applyHero(m === "domain" ? "domain" : m === "ops" ? "ops" : m === "compare" ? "compare" : "insurance");
  if (push !== false){ try { history.pushState({mode:m}, "", "?mode=" + m); } catch (e) { } }
  updateStory();
  renderDecisionTable(LAST_RUN);
  if (m === "ops") initOps();
  else if (m === "domain") initDomain();
  else if (keepClaim && LAST) runClaim(LAST.state, LAST.gold, LAST.nonLatin, true, LAST.lang);
}
window.onpopstate = () => setMode(modeFromLocation(), false, false);

function setDot(el, cls, label){
  el.className = "dot " + cls;
  el.title = label;
  el.setAttribute("aria-label", label);
  const pill = document.querySelector(".status-pill");
  const status = $("serviceStatus");
  if (!pill || !status) return;
  const dots = ["dotLaya", "dotDecider", "dotStudio"].map(id => $(id));
  const down = dots.filter(dot => dot && dot.classList.contains("down")).length;
  const busy = dots.some(dot => dot && dot.classList.contains("busy"));
  const allUp = dots.every(dot => dot && dot.classList.contains("up"));
  pill.dataset.state = down ? "down" : busy ? "busy" : allUp ? "up" : "unknown";
  status.textContent = down ? `${down} service${down === 1 ? "" : "s"} down`
    : busy ? "Studio training" : allUp ? "All systems live" : "Checking services";
}
async function health(){
  for (const [base, dot, label] of [[LAYA, "dotLaya", "Laya service"], [DECBASE, "dotDecider", "decider service"], [LAYA + "/studio", "dotStudio", "studio"]]){
    const el = $(dot);
    if (!el) continue;                       // a missing indicator must never break the page
    try {
      const r = await fetch(base + "/health", {signal: AbortSignal.timeout(10000)});
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j = await r.json().catch(() => ({}));
      if (dot === "dotStudio"){
        const job = j.job || j.state || "idle";
        const training = job === "training" || job === "evaluating";
        const gpu = j.gpu ? ` — ${Number(j.gpu.free_gib).toFixed(1)} GiB GPU free` : "";
        setDot(el, training ? "busy" : "up", `studio ${job}${gpu}`);
      } else {
        setDot(el, "up", label + " up");
      }
    } catch (e) {
      setDot(el, "down", label + " down (" + e.message + ")");
    }
  }
}

function fillStat(id, subId, avg, k, n){
  $(id).textContent = avg === undefined ? "n/a" : fmtP(avg);
  if (subId) $(subId).textContent = k !== undefined && n ? id.replace("st-", "") + ": " + k + "/" + n + " " + fmtCI(k, n) : id.replace("st-", "") + ": unavailable";
}
fetch(LAYA + "/stats").then(r=>r.json()).then(s => {
  const n = s.n_rows || 500, rac = s.rows_all_correct || {};
  fillStat("st-zero", "st-zero-sub", s.zero, rac.zero, n);
  fillStat("st-ft", "st-ft-sub", s.ft, rac.ft, n);
  fillStat("st-dec", "st-dec-sub", s.dec, rac.dec, n);
  if (s.rules !== undefined) fillStat("st-rules", "st-rules-sub", s.rules, rac.rules, n);
  else { $("st-rules").textContent = "n/a"; $("st-rules-sub").textContent = "rules: unavailable"; }
  $("all-seven").textContent = `${rac.zero ?? "?"}/${n} → ${rac.ft ?? "?"}/${n} all 7`;
  $("dec-seven").textContent = `${rac.dec ?? "?"}/${n} all 7`;
  $("cav-ft").textContent = CAVEAT_100;
  const hl = $("heroLine");
  if (s.zero !== undefined && s.ft !== undefined){
    hl.innerHTML = `Measured on ${n} sealed holdout claims: Laya out-of-the-box gets <b>${fmtP(s.zero)}</b> of decisions right (${rac.zero ?? "?"}/${n} all seven); after a ~15-minute fine-tune on 12,000 past claims: <b>${fmtP(s.ft)}</b> avg, <b>${rac.ft ?? "?"}/${n}</b> all seven. <span class="small">Same engine, no code changes — only training.</span>`;
    hl.hidden = MODE !== "day1" && MODE !== "after";
  }
  if (s.version) $("verLine").textContent = " · version " + esc(s.version);
}).catch(()=>{
  for (const id of ["st-zero","st-ft","st-dec","st-rules"]) $(id).textContent = "n/a";
  $("all-seven").textContent = $("dec-seven").textContent = "holdout unavailable";
  $("cav-ft").textContent = CAVEAT_100;
});
