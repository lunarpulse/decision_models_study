// ======================= Ops floor (STP + adjuster queue) =======================
let OPS = null, OPS_TAU = 0.8, OPS_ACTIONS = {}, OPS_ARM = "ft", OPS_VIEW = "review", CAL_RENDERED = false;
const OPS_ACT_LABEL = {auto: "auto-paid", flag: "flagged → SIU", review: "adjuster review"};
const OPS_VIEW_LABEL = {review: "Adjuster review", flag: "Flagged → SIU", auto: "Auto-paid (spot-check)"};

function opsAnswers(c){ return (c.arms[OPS_ARM] || {}).answers || {}; }
function opsFraudP(c){
  const a = opsAnswers(c).fraud_review;
  if (!a) return null;
  if (a.noul !== undefined) return a.noul;
  if (a.probabilities) return Math.max(...Object.values(a.probabilities));
  return null;
}
function opsCertaintyNote(){
  const claims = OPS.claims;
  const ps = claims.map(opsFraudP).filter(p => p !== null);
  if (!ps.length) return "";
  if (ps.every(p => p === 0 || p === 1))
    return "this engine is certain on every claim here — τ has no effect (see calibration caveat)";
  return "";
}

function buildOpsShell(){
  $("opsfloor").innerHTML = `
  <section class="section" aria-labelledby="opsControlsTitle">
    <div class="section-head"><h2 id="opsControlsTitle">Portfolio controls</h2></div>
    <div class="card ops-controls">
      <label><strong>Engine:</strong> <select id="opsEngine">${OPS_ARMS.map(([v,l]) => `<option value="${v}">${l}</option>`).join("")}</select></label>
      <label><strong>Auto-approve cutoff (τ): <span id="tauVal">${OPS_TAU.toFixed(2)}</span></strong> <input type="range" id="tauSlider" min="50" max="95" value="${Math.round(OPS_TAU*100)}"></label>
      <label><strong>Claims/year:</strong> <input type="number" id="volIn" value="120000"></label>
    </div>
  </section>
  <section class="section" aria-labelledby="opsCountersTitle">
    <div class="section-head"><h2 id="opsCountersTitle">Measured portfolio</h2></div>
    <div id="opsCounters" class="ops-counters"><p class="small">loading the measured 500-claim portfolio…</p></div>
    <p class="small ops-projection" id="opsProj">—</p>
    <p class="callout callout--warning" id="tauNote" hidden></p>
  </section>
  <section class="section" aria-labelledby="opsQueueTitle">
    <div class="section-head">
      <h2 id="opsQueueTitle">Claim queue — the engine's disposition, and your override</h2>
      <p class="small">Each claim gets one disposition. <b>Auto-paid</b>: straight through, no person. <b>Flagged → SIU</b>:
        held for the fraud unit (p(fraud) ≥ τ). <b>Adjuster review</b>: a person decides (not covered, or more than one touch
        expected). The engine proposes; the buttons override; every counter above follows.</p>
    </div>
    <div class="ops-queue-controls">
      <span class="small"><strong>Show what the engine sent to:</strong></span>
      <span id="opsViews" class="segmented" role="group" aria-label="Engine disposition"></span>
      <button type="button" class="btn btn--secondary btn--sm" id="opsReset" hidden>Reset overrides</button>
    </div>
    <div class="table-wrap tablewrap" role="region" aria-label="Claim queue" tabindex="0"><table class="table table--sticky"><thead id="opsQueueHead"></thead><tbody id="opsQueueBody"></tbody></table></div>
    <p class="small" id="opsQueueFoot"></p>
  </section>
  <section class="section" aria-labelledby="opsCalTitle">
    <div class="section-head"><h2 id="opsCalTitle">Calibration — fraud flag</h2></div>
    <div class="card">
      <div id="opsCal"></div>
      <p class="small">share of claims in this probability bin that were actually fraud (n below); perfect calibration sits on the diagonal.</p>
      <p class="callout callout--warning" id="calCaveat" hidden></p>
    </div>
  </section>`;
  $("tauSlider").oninput = (e) => { OPS_TAU = e.target.value/100; $("tauVal").textContent = OPS_TAU.toFixed(2); updateOps(); };
  $("opsEngine").onchange = (e) => { OPS_ARM = e.target.value; updateOps(); };
  $("volIn").oninput = () => updateOps();
  $("opsViews").onclick = (e) => { const b = e.target.closest("[data-view]"); if (b){ OPS_VIEW = b.dataset.view; updateOps(); } };
  $("opsReset").onclick = () => { OPS_ACTIONS = {}; updateOps(); };
}

// What the selected engine does with a claim at cutoff τ: hold it for the fraud unit, pay it
// straight through, or hand it to an adjuster. Touches is a near-integer score (1.0001): round it.
function opsDefault(c){
  const a = opsAnswers(c), pF = opsFraudP(c);
  if (pF === null) return "review";
  if (pF >= OPS_TAU) return "flag";
  const touches = a.expected_touches ? a.expected_touches.score : null;
  const covered = a.coverage_eligibility && a.coverage_eligibility.choice === "covered";
  return (touches !== null && Math.round(touches) <= 1 && covered) ? "auto" : "review";
}
function opsAction(c){ return OPS_ACTIONS[c.id] || opsDefault(c); }

function opsRow(c){
  const g = c.gold, m = c.meta, a = opsAnswers(c);
  const pF = opsFraudP(c);
  const touches = a.expected_touches ? a.expected_touches.score : null;
  const def = opsDefault(c), act = opsAction(c), overridden = act !== def;
  const routing = a.routing ? a.routing.choice : null;
  const routingOK = routing !== null && routing === g.routing;
  const fraudOK = pF === null ? false : ((pF >= 0.5) === !!m.fraud);
  const btn = (v, label) => `<button type="button" class="btn btn--secondary btn--sm" ${act === v ? "disabled" : ""} onclick="opsAct('${esc(c.id)}','${v}')">${label}</button>`;
  return `<tr class="ops-queue-row${overridden ? " is-changed" : ""}">
    <td class="small" data-label="Claim">${esc(c.id.replace("ins-",""))}</td>
    <td class="small" data-label="Category">${esc(m.cat)}</td>
    <td class="small ops-number" data-label="Amount">${usd(m.amount)}</td>
    <td class="small" data-label="Routing" title="${esc(String(routing))}">${routing===null?"—":esc(humanize(routing))} ${routingOK?"✓":"✗"}</td>
    <td class="small ops-number" data-label="p(fraud)"${pF!==null?` title="raw ${pF}"`:""}>${pF===null?"—":fmtP(pF)} ${fraudOK?"✓":"✗"}</td>
    <td class="small" data-label="Actually">${m.fraud ? '<b class="ops-fraud">fraud</b>' : "legit"}</td>
    <td class="small ops-touches" data-label="Touches pred/gold"${touches!==null?` title="raw ${touches}"`:""}>${touches===null?"—":Math.round(touches)}/${g.expected_touches}</td>
    <td><span class="chip chip--${act === "auto" ? "success" : act === "flag" ? "danger" : "warning"}">${OPS_ACT_LABEL[act]}</span>${overridden ? `<br><span class="small" title="the engine proposed: ${OPS_ACT_LABEL[def]}">↺ engine said ${OPS_ACT_LABEL[def]}</span>` : ""}</td>
    <td><div class="ops-row-actions">${btn("auto", "Auto-pay")}${btn("flag", "Flag fraud")}${btn("review", "To adjuster")}</div></td></tr>`;
}
function opsAct(id, act){
  const c = OPS.claims.find(x => x.id === id);
  if (c && act === opsDefault(c)) delete OPS_ACTIONS[id]; else OPS_ACTIONS[id] = act;
  updateOps();
}

function renderOpsCal(){
  if (CAL_RENDERED || !OPS.summary.calibration) return;
  CAL_RENDERED = true;
  let anySharp = false;
  $("opsCal").innerHTML = Object.entries(OPS.summary.calibration).map(([arm, bins]) => {
    const sharp = bins.length && bins.every(b => b.avg_p === 0 || b.avg_p === 1);
    if (sharp && (arm === "ft" || arm === "dec_ft")) anySharp = true;
    return `<div class="calrow"><span class="k" title="${arm}">${esc(ARM_LABEL[arm] || arm)}</span>` +
      bins.map(b => `<span class="calbin" title="p ${b.lo}–${b.hi}: said ${(100*b.avg_p).toFixed(0)}%, actually fraud ${(100*b.acc).toFixed(0)}% of ${b.n}">${(100*b.acc).toFixed(0)}<small>${b.n}</small></span>`).join("") +
      `</div>`;
  }).join("");
  $("calCaveat").textContent = anySharp
    ? "the fine-tuned engines are certain on every claim here (every probability is exactly 0 or 1) — read them as decisions, not odds, until recalibrated on real data."
    : "";
  $("calCaveat").hidden = !anySharp;
}

function updateOps(){
  const claims = OPS.claims;
  const n = {auto: 0, flag: 0, review: 0}, amt = {auto: 0, flag: 0, review: 0};
  const views = {auto: [], flag: [], review: []};
  let autoAll = 0, missed = 0, missed$ = 0, tot$ = 0, held$ = 0, fp = 0, fp$ = 0, overrides = 0;
  for (const c of claims){
    const m = c.meta, a = opsAnswers(c), def = opsDefault(c), act = OPS_ACTIONS[c.id] || def;
    if (act !== def) overrides++;
    views[def].push(c);
    tot$ += m.amount; n[act]++; amt[act] += m.amount;
    if (act === "auto"){
      if (Object.keys(c.gold).length && allCorrect(a, c.gold)) autoAll++;
      if (m.fraud){ missed++; missed$ += m.amount; }
    } else if (act === "flag"){
      if (m.fraud) held$ += m.amount; else { fp++; fp$ += m.amount; }
    }
  }
  const vol = +$("volIn").value || 0, per = claims.length ? vol/claims.length : 0;
  const fraudShare = claims.length ? claims.filter(c => c.meta.fraud).length / claims.length : 0;
  const autoAllPct = n.auto ? (100*autoAll/n.auto).toFixed(1)+"%" : "—";
  $("opsCounters").innerHTML = `
    <div class="card stat"><div class="stat__value">${claims.length}</div><div class="stat__label">claims in the sealed holdout · ${usd(tot$)} claimed</div></div>
    <div class="card stat"><div class="stat__value">${(100*n.auto/claims.length).toFixed(1)}%</div><div class="stat__label">straight-through: auto-paid, no person (${n.auto} claims, ${usd(amt.auto)})</div></div>
    <div class="card stat"><div class="stat__value">${autoAllPct}</div><div class="stat__label">auto-paid claims where the engine's 7 decisions were all right (${autoAll}/${n.auto})</div></div>
    <div class="card stat${missed ? " card--danger" : ""}"><div class="stat__value">${missed}</div><div class="stat__label">fraud claims paid out unattended (${usd(missed$)} leaked)</div></div>
    <div class="card stat"><div class="stat__value">${usd(held$)}</div><div class="stat__label">fraud $ held for the SIU (${n.flag} flagged; ${fp} legit customers false-flagged, ${usd(fp$)})</div></div>
    <div class="card stat"><div class="stat__value">${n.review}</div><div class="stat__label">claims on adjusters' desks (${usd(amt.review)}) — the human workload</div></div>`;
  $("opsProj").textContent = `Illustrative at this synthetic mix (${(100*fraudShare).toFixed(1)}% fraud): ` +
    `${Math.round(per*n.auto).toLocaleString("en-US")} claims/yr straight through; ` +
    `${Math.round(per*n.review).toLocaleString("en-US")} claims/yr to adjusters; ` +
    `${usd(per*held$)}/yr held for fraud investigation instead of auto-paid.`;
  const note = opsCertaintyNote();
  $("tauNote").hidden = !note;
  $("tauNote").textContent = note;
  $("opsViews").innerHTML = ["review", "flag", "auto"].map(v =>
    `<button type="button" class="btn btn--secondary btn--sm${OPS_VIEW === v ? " on chip--selected" : ""}" data-view="${v}" aria-pressed="${OPS_VIEW === v}">${OPS_VIEW_LABEL[v]} (${views[v].length})</button>`).join("");
  $("opsReset").hidden = !overrides;
  $("opsReset").textContent = `Reset ${overrides} override${overrides === 1 ? "" : "s"}`;
  $("opsQueueHead").innerHTML = `<tr><th scope="col">claim</th><th scope="col">cat</th><th scope="col">amount</th><th scope="col">routing (${esc(ARM_LABEL[OPS_ARM])})</th><th scope="col">p(fraud)</th><th scope="col">actually</th><th scope="col">touches pred/gold</th><th scope="col">disposition</th><th scope="col">override</th></tr>`;
  const rows = views[OPS_VIEW].slice()
    .sort((a, b) => ((opsFraudP(b) ?? -1) - (opsFraudP(a) ?? -1)) || (b.meta.amount - a.meta.amount));
  $("opsQueueBody").innerHTML = rows.slice(0, 14).map(opsRow).join("") ||
    `<tr><td colspan="9" class="small">no claims — the engine sent nothing here at τ=${OPS_TAU.toFixed(2)}</td></tr>`;
  $("opsQueueFoot").textContent = rows.length
    ? `showing ${Math.min(14, rows.length)} of ${rows.length}, highest p(fraud) first, then largest amount. ` +
      `Overridden rows stay in place, shaded, with ↺ showing what the engine proposed.`
    : "";
}
async function initOps(){
  if (!$("opsEngine")){ buildOpsShell(); CAL_RENDERED = false; }
  if (!OPS){
    try {
      OPS = await fetch(LAYA + "/portfolio?lite=1").then(r => {
        if (!r.ok) throw new Error("HTTP " + r.status); return r.json();
      });
      renderOpsCal();
    } catch (e) {
      $("opsfloor").innerHTML = `<div class="card"><p>portfolio data not available (${esc(String(e))}).</p></div>`;
      const b = document.createElement("button");
      b.className = "btn btn--secondary ops-retry"; b.textContent = "Retry"; b.onclick = () => { OPS = null; initOps(); };
      $("opsfloor").appendChild(b);
      return;
    }
  }
  updateOps();
}


