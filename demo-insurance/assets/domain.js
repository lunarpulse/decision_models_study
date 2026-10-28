// ============ Domain Builder v3: change the rulebook, re-teach the model live, compare ============
let DOMS = null, DB = null, DB_WATCH = null, DB_CLOCK = null;
const DOM_META = {
  support_tickets:      {name:"Support desk", blurb:"SaaS helpdesk tickets: which team, abuse review, urgency, refund eligibility and amount, vendor chargeback, agent effort"},
  logistics_exceptions: {name:"Logistics exceptions", blurb:"Damaged, lost, held or late shipments: which desk, compliance review, urgency, liability, recovery amount, sub-carrier recovery"},
  hr_exceptions:        {name:"HR exceptions", blurb:"Leave, benefits, payroll and conduct requests: which desk, ethics review, urgency, policy scope, amount, external party"},
};
const ARCH_TITLE = {routing:"Route to", risk_flag:"Flag for review?", urgency:"Urgency", eligibility:"Eligible?",
  money_band:"Amount band", third_party:"Recover from a third party?", touches:"Handling effort"};
const DB_STEPS = ["Your model today", "Change a rule", "Re-teach", "What changed", "Try to break it"];
// Measured offline on all 500 sealed test cases per preset (measure_policy_teach.py; DEVELOPMENT_LOG Phase 10):
// decisions the rule changes right before → after, decisions it leaves alone right after, all-7 after, train s.
const DB_MEASURED = {
  support_tickets: {
    reassign: {rule:"Account tickets → trust and safety", changed_before:"0/116", changed_after:"116/116", kept_after:"3,363/3,384", all7_before:372, all7_after:490, train_s:49},
    vip:      {rule:"Premium tier → at least urgent",   changed_before:"0/107", changed_after:"107/107", kept_after:"3,362/3,393", all7_before:380, all7_after:486, train_s:59},
    risk:     {rule:"Flag at 1 warning sign (was 2)",   changed_before:"2/886", changed_after:"886/886", kept_after:"2,608/2,614", all7_before:261, all7_after:496, train_s:61}},
  logistics_exceptions: {
    reassign: {rule:"Customs → contract compliance",    changed_before:"0/111", changed_after:"111/111", kept_after:"3,372/3,389", all7_before:388, all7_after:488, train_s:52},
    vip:      {rule:"Premium tier → at least urgent",   changed_before:"0/88",  changed_after:"88/88",   kept_after:"3,404/3,412", all7_before:410, all7_after:496, train_s:46},
    risk:     {rule:"Flag at 1 warning sign (was 2)",   changed_before:"0/843", changed_after:"843/843", kept_after:"2,655/2,657", all7_before:273, all7_after:498, train_s:48}},
  hr_exceptions: {
    reassign: {rule:"Conduct → ethics review",          changed_before:"0/123", changed_after:"123/123", kept_after:"3,361/3,377", all7_before:371, all7_after:488, train_s:61},
    vip:      {rule:"Premium tier → at least urgent",   changed_before:"0/95",  changed_after:"95/95",   kept_after:"3,382/3,405", all7_before:399, all7_after:491, train_s:59},
    risk:     {rule:"Flag at 1 warning sign (was 2)",   changed_before:"1/899", changed_after:"899/899", kept_after:"2,584/2,601", all7_before:257, all7_after:485, train_s:54}},
};
const DB_PROD_NOTE = "about 7 minutes per business on this GPU (424–437 s measured; train_prod_ckpt.sh)";
// Production models on the 3 hand-reworded cases per business (measured via /studio/compare, DEVELOPMENT_LOG Phase 10).
const DB_PROBES = {
  support_tickets:      {all7:"0/3", decisions:"16/21", unread:"9/21"},
  logistics_exceptions: {all7:"3/3", decisions:"21/21", unread:"8/21"},
  hr_exceptions:        {all7:"2/3", decisions:"20/21", unread:"9/21"},
};

function studioURL(p){ return LAYA + "/studio" + p; }
async function studioCall(path, body, token){
  const opt = body === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)};
  if (token) opt.headers["X-Studio-Token"] = token;
  const r = await fetch(studioURL(path), opt);
  let data = {};
  try { data = await r.json(); } catch (e) { /* non-JSON error body */ }
  return {code: r.status, data};
}
const dbNoun = () => (DB && DB.s ? DB.s.noun_plural.replace(/s$/, "") : "case");
const dbNouns = () => (DB && DB.s ? DB.s.noun_plural : "cases");
function dbArch(qid){ const a = DB.s.archetypes || {}; for (const k in a) if (a[k] === qid) return k; return ""; }
function dbTitle(qid){ return ARCH_TITLE[dbArch(qid)] || humanize(qid); }
function dbQids(){ return DB.s.stages.flatMap(st => st.questions); }
function dbVal(qid, v){
  if (v === null || v === undefined) return "—";
  if (v === "unparsed") return "can't read it";
  if (typeof v === "boolean") return v ? "yes" : "no";
  const q = DB.s.questions[qid] || {};
  if (typeof v === "number" && Array.isArray(q.criteria)) return String(q.criteria[v] ?? v).split(/ \(| \//)[0];
  return humanize(v).replace(/\d{4,}/g, d => Number(d).toLocaleString("en-US"));
}
function dbMark(ok){ return ok ? `<span class="ok">✓</span>` : `<span class="no">✗</span>`; }

// ---- ticket text: highlight the facts the rules hinge on; one-click edits ----
function dbRe(name){ try { return new RegExp(DB.s.text.parsers[name], "d"); } catch (e) { return null; } }
function dbGroup(text, name){ const re = dbRe(name); const m = re && re.exec(text); return m ? m[1] : null; }
function dbFacts(text){
  const T = DB.s.text, out = [];
  const cat = dbGroup(text, "ref"), tier = dbGroup(text, "tier"), amt = dbGroup(text, "amount"), start = dbGroup(text, "start");
  if (cat) out.push(cat.toLowerCase());
  if (tier) out.push(tier);
  if (amt) out.push("USD " + amt);
  if (text.includes(T.doc_missing_marker)) out.push("no evidence");
  if (start){
    const days = Math.round((new Date(T.today) - new Date(start)) / 864e5);
    if (days >= 0 && days <= T.fresh_days) out.push(`started ${days} days ago`);
  }
  return out.join(" · ");
}
function dbTicketHTML(text){
  const T = DB.s.text, spans = [];
  for (const n of ["ref", "start", "incident", "amount", "tier"]){
    const re = dbRe(n); const m = re && re.exec(text);
    if (m && m.indices && m.indices[1]) spans.push(m.indices[1]);
  }
  for (const list of Object.values(T.things)) for (const th of list){
    const i = text.indexOf(th); if (i >= 0) spans.push([i, i + th.length]);
  }
  const mi = text.indexOf(T.doc_missing_marker);
  if (mi >= 0) spans.push([mi, mi + T.doc_missing_marker.length]);
  spans.sort((a, b) => a[0] - b[0]);
  let html = "", pos = 0;
  for (const [s, e] of spans){
    if (s < pos) continue;
    html += esc(text.slice(pos, s)) + "<b>" + esc(text.slice(s, e)) + "</b>"; pos = e;
  }
  return html + esc(text.slice(pos));
}
function dbSetGroup(text, name, value){
  const re = dbRe(name); const m = re && re.exec(text);
  if (!m || !m.indices || !m.indices[1]) return text;
  const [s, e] = m.indices[1];
  return text.slice(0, s) + value + text.slice(e);
}
function dbDaysBefore(iso, days){
  const d = new Date(iso + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() - days); return d.toISOString().slice(0, 10);
}
function dbMakeCat(text, cat){
  const T = DB.s.text;
  let done = false;
  for (const list of Object.values(T.things)){
    for (const th of list) if (text.includes(th)){ text = text.replace(th, T.things[cat][0]); done = true; break; }
    if (done) break;
  }
  return dbSetGroup(text, "ref", cat.toUpperCase());
}
function dbNoDocs(text){
  const T = DB.s.text, i = text.indexOf(T.doc_ok_prefix);
  if (i < 0) return text;
  const j = text.indexOf(".", i);
  return text.slice(0, i) + T.doc_missing + (j >= 0 ? text.slice(j + 1) : "");
}

// ---- page skeleton ----
let DB_TAUGHT = {};   // {domain: finished-timestamp | null}: which businesses run a re-taught model now
function dbBadgeText(k){
  return DB_TAUGHT[k] ? `● re-taught model active (since ${String(DB_TAUGHT[k]).slice(11, 16)})` : "● fresh — your model only";
}
function dbBadges(){
  document.querySelectorAll(".db-dom").forEach(b => {
    const t = b.querySelector(".db-badge"); if (!t) return;
    t.textContent = dbBadgeText(b.dataset.dom);
    t.classList.toggle("taught", !!DB_TAUGHT[b.dataset.dom]);
    t.classList.toggle("chip--warning", !!DB_TAUGHT[b.dataset.dom]);
    t.classList.toggle("chip--success", !DB_TAUGHT[b.dataset.dom]);
  });
}
function dbPickerHTML(){
  return `<div class="db-pick" role="radiogroup" aria-label="pick a business">${Object.keys(DOMS).map(k => {
    const m = DOM_META[k] || {name:humanize(k), blurb:""};
    const on = DB && DB.domain === k;
    return `<button type="button" class="db-dom card${on ? " on" : ""}" role="radio" aria-checked="${on}" data-dom="${esc(k)}">
      <span class="t">${esc(m.name)}</span><span class="small">${esc(m.blurb)}</span>
      <span class="db-badge badge ${DB_TAUGHT[k] ? "taught chip--warning" : "chip--success"}">${esc(dbBadgeText(k))}</span></button>`;
  }).join("")}</div>`;
}
// What is loaded for this business right now — and the presenter's way back to a fresh start.
function dbStateRender(){
  const box = $("dbState"); if (!box || !DB || !DB.s) return;
  const R = DB.result;
  if (DB.running) box.innerHTML = `<div class="db-state run callout callout--warning"><b>Re-teaching now.</b>
    Your model (trained once on 2,000 past ${dbNouns()}) stays untouched; the re-taught copy replaces the previous one when it finishes.</div>`;
  else if (R) box.innerHTML = `<div class="db-state taught callout callout--warning"><b>A re-taught model is active</b> —
    “${esc(R.sentence)}” (finished ${esc(R.finished || "")}). Your model is unchanged; steps ④–⑤ show both.
    <button type="button" class="btn btn--secondary btn--sm" id="dbResetOne">↺ Reset to a fresh start — presenter</button></div>`;
  else box.innerHTML = `<div class="db-state fresh callout callout--success"><b>Fresh start.</b> Only your model is
    loaded — trained <i>before this demo</i> on 2,000 past ${dbNouns()} whose answers came from today's rulebook;
    nothing has been re-taught in this session.</div>`;
  const b = $("dbResetOne"); if (b) b.onclick = () => dbReset(DB.domain);
}
async function dbReset(target){
  const name = target === "all" ? "every business" : ((DOM_META[target] || {}).name || target);
  if (!confirm(`Reset ${name} to a fresh start? The re-taught model and its result are deleted; your production model stays.`)) return;
  const tok = sessionStorage.getItem("studioToken") || prompt("Studio token (presenter only):") || "";
  let r;
  try { r = await studioCall("/reset", {domain: target}, tok); }
  catch (e){ alert("Network error — the studio is unreachable; try again."); return; }
  if (r.data.error_kind === "token"){ sessionStorage.removeItem("studioToken"); alert("Wrong or missing studio token."); return; }
  sessionStorage.setItem("studioToken", tok);
  if (r.code !== 200){ alert(dbFailText(r.data)); return; }
  for (const [k, v] of Object.entries(r.data.taught || {})) DB_TAUGHT[k] = v ? v.finished : null;
  if (DB && (target === "all" || target === DB.domain)) dbPick(DB.domain);
  else dbBadges();
}
function dbStepsHTML(){
  return `<nav class="db-steps" aria-label="demo steps">${DB_STEPS.map((t, i) =>
    `<button type="button" class="chip" data-step="${i + 1}">${i + 1} · ${t}</button>`).join("")}</nav>`;
}
function dbSteps(done){   // highlight steps 1..done as reached
  document.querySelectorAll(".db-steps button").forEach(b => {
    const reached = Number(b.dataset.step) <= done;
    b.classList.toggle("done", reached);
    b.setAttribute("aria-label", `${b.textContent}${reached ? " — reached" : ""}`);
  });
}
function dbScroll(el){
  el.scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block:"start"});
}
function dbRender(){
  const el = $("domainfloor");
  el.innerHTML = `<div id="dbLive"></div>` + dbPickerHTML() + dbStepsHTML() + `<div id="dbState"></div>` +
    dbAct1HTML() + dbAct2HTML() + dbAct3HTML() +
    `<section class="db-act section" id="dbAct4" hidden></section>` + dbAct5HTML() + dbFineHTML();
  el.querySelectorAll(".db-dom").forEach(b => b.onclick = () => dbPick(b.dataset.dom));
  el.querySelectorAll(".db-steps button").forEach(b => b.onclick = () => {
    const t = $("dbAct" + b.dataset.step); if (t && !t.hidden) dbScroll(t);
  });
  dbRenderShow();
  dbWireCards();
  $("dbTeach").onclick = dbTeach;
  dbRenderMutators();
  $("dbAskBtn").onclick = dbAsk;
  dbSteps(1);
  dbStateRender();
}

// ---- act 1: your model today ----
function dbAct1HTML(){
  const B = DB.s.baseline, n = B.n, z = B.zero, p = B.prod;
  const pct = (x) => x == null ? "—" : (100 * x).toFixed(1) + "%";
  return `<section class="db-act section" id="dbAct1"><header class="section-head"><p class="kicker">Step 1 · Your model today</p>
    <h2>Out of the box, AI doesn't know your rulebook. Your model does.</h2>
    <p class="lead">Every ${dbNoun()} needs seven decisions: where it goes, whether to flag it, how urgent it is,
      whether it qualifies, how much, whether someone else pays, and how much work it takes. Scored on ${n} past
      ${dbNouns()} neither model trained on, against the written rulebook:</p></header>
    <div class="db-vs">
      <div class="db-stat stat card card--muted"><div class="big stat__value">${z ? z.all7 : "—"}<small> / ${n}</small></div>
        <div class="lbl stat__label">Out-of-the-box AI · Laya, general model, no training</div>
        <div class="lbl stat__delta">${dbNouns()} with all 7 decisions right · ${pct(z && z.avg)} of single decisions</div></div>
      <div class="db-arrow" aria-hidden="true">→</div>
      <div class="db-stat stat card card--success"><div class="big stat__value">${p ? p.all7 : "…"}<small> / ${n}</small></div>
        <div class="lbl stat__label">Your model · the same Laya, trained before this demo on 2,000 past ${dbNouns()} (~7 min, once)</div>
        <div class="lbl stat__delta">${dbNouns()} with all 7 decisions right · ${pct(p && p.avg)} of single decisions</div></div>
    </div>
    ${B.dec ? `<p class="small">For scale: decider-4b, a 4-billion-parameter generalist with no training, gets ${B.dec.all7} / ${n} (${pct(B.dec.avg)} of single decisions).</p>` : ""}
    ${DB.s.prod_ready ? "" : `<p class="note">No production model on this host yet — run <code>train_prod_ckpt.sh</code>; re-teaching needs it.</p>`}
    <div id="dbShow"></div></section>`;
}
function dbRenderShow(){
  const list = DB.s.showcase || [];
  const box = $("dbShow");
  if (!list.length){ box.innerHTML = ""; return; }
  const c = list[DB.showIdx % list.length];
  const qids = dbQids();
  const zOK = qids.filter(q => c.zero[q] === c.gold[q]).length;
  const pOK = c.prod ? qids.filter(q => c.prod[q] === c.gold[q]).length : null;
  box.innerHTML = `<div class="db-showhead"><h3>One ${dbNoun()}, seven decisions</h3>
      <button type="button" class="btn btn--secondary btn--sm" id="dbShowNext">another ${dbNoun()} ↻</button>
      <button type="button" class="btn btn--secondary btn--sm" id="dbShowTry">try it yourself ↓</button></div>
    <div class="db-ticket card card--muted">${dbTicketHTML(c.state)}</div>
    <div class="table-wrap" role="region" aria-label="Showcase decisions" tabindex="0"><table class="table db-dt"><thead><tr><th>decision</th><th>out of the box</th><th>your model</th><th>rulebook</th></tr></thead><tbody>${
      qids.map(q => `<tr><td>${esc(dbTitle(q))}</td>
        <td>${dbMark(c.zero[q] === c.gold[q])} ${esc(dbVal(q, c.zero[q]))}</td>
        <td>${c.prod ? dbMark(c.prod[q] === c.gold[q]) + " " + esc(dbVal(q, c.prod[q])) : "…"}</td>
        <td>${esc(dbVal(q, c.gold[q]))}</td></tr>`).join("")}</tbody>
      <tfoot><tr><td></td><td class="no">${zOK} / 7</td><td class="ok">${pOK === null ? "…" : pOK + " / 7"}</td><td></td></tr></tfoot></table></div>`;
  $("dbShowNext").onclick = () => { DB.showIdx++; dbRenderShow(); };
  $("dbShowTry").onclick = () => dbTry(c.state, true);
}

// ---- act 2: change a rule ----
function dbAct2HTML(){
  return `<section class="db-act section" id="dbAct2"><header class="section-head"><p class="kicker">Step 2 · The business changes</p>
    <h2>Pick a rule change — every value is yours to set</h2>
    <p class="small">The rulebook re-decides every past ${dbNoun()} under the new rule; the ones that change become the lesson.</p></header>
    <div class="db-pol" role="radiogroup" aria-label="rule changes">${DB.s.presets.map(dbCardHTML).join("")}</div>
    <div id="dbImpact"><p class="small">Pick a change above to see what it touches.</p></div></section>`;
}
function dbSel(kind, name, values, cur, label){
  return `<select data-kind="${kind}" data-param="${name}" aria-label="${esc(kind + " " + name)}">${values.map(v =>
    `<option value="${esc(String(v))}"${String(v) === String(cur) ? " selected" : ""}>${esc(label(v))}</option>`).join("")}</select>`;
}
function dbRuleHTML(kind, p){
  const C = DB.s.choices[kind], nouns = dbNouns();
  if (kind === "reassign")
    return `${dbSel(kind, "cat", C.cat, p.cat, humanize)} ${nouns} go to ${dbSel(kind, "unit", C.unit, p.unit, humanize)}`;
  if (kind === "vip")
    return `${dbSel(kind, "tier", C.tier, p.tier, v => v)}-tier ${nouns} are always at least ${dbSel(kind, "level", C.level, p.level, v => DB.s.urgency_names[v])}`;
  return `Flag for review at ${dbSel(kind, "markers", C.markers, p.markers, String)} warning sign(s)`;
}
function dbTodayText(kind, p){
  const cur = DB.s.current;
  if (kind === "reassign") return `today: ${humanize(p.cat)} ${dbNouns()} go to ${humanize(cur.units[p.cat])}`;
  if (kind === "vip") return "today: no tier gets a minimum urgency";
  return `today: ${cur.flag_markers} of these — ${cur.warning_signs.join(" · ")}`;
}
function dbCardHTML(pre){
  const on = DB.pol && DB.pol.kind === pre.kind;
  const p = on ? DB.pol.params : pre.params;
  return `<div class="db-card card${on ? " on" : ""}" role="radio" aria-checked="${on}" tabindex="0" data-kind="${pre.kind}">
    <div class="t">${esc(pre.title)}</div>
    <div class="story">“${esc(pre.story)}”</div>
    <div class="db-rule">${dbRuleHTML(pre.kind, p)}</div>
    <div class="db-today">${esc(dbTodayText(pre.kind, p))}</div></div>`;
}
function dbWireCards(){
  document.querySelectorAll("#dbAct2 .db-card").forEach(card => {
    card.onclick = (ev) => { if (ev.target.closest("select")) return; dbChoose(card.dataset.kind); };
    card.onkeydown = (ev) => {
      if ((ev.key === "Enter" || ev.key === " ") && !ev.target.closest("select")){ ev.preventDefault(); dbChoose(card.dataset.kind); }
    };
    card.querySelectorAll("select").forEach(sel => sel.onchange = () => dbChoose(card.dataset.kind));
  });
}
function dbChoose(kind){
  const card = document.querySelector(`#dbAct2 .db-card[data-kind="${kind}"]`);
  const params = {};
  card.querySelectorAll("select").forEach(sel => {
    const v = sel.value; params[sel.dataset.param] = /^\d+$/.test(v) ? Number(v) : v;
  });
  DB.pol = {kind, params};
  document.querySelectorAll("#dbAct2 .db-card").forEach(c => {
    const on = c.dataset.kind === kind;
    c.classList.toggle("on", on); c.setAttribute("aria-checked", String(on));
  });
  card.querySelector(".db-today").textContent = dbTodayText(kind, params);
  dbRenderMutators();
  dbImpact();
}
async function dbImpact(){
  const box = $("dbImpact"), want = JSON.stringify(DB.pol), domain = DB.domain;
  box.innerHTML = `<p class="small thinking">re-deciding every past ${dbNoun()} under the new rule…</p>`;
  let r;
  try { r = await studioCall("/impact", {domain, policy: DB.pol}); }
  catch (e){ box.innerHTML = `<p class="small no">network error — pick the change again</p>`; return; }
  if (!DB || DB.domain !== domain || JSON.stringify(DB.pol) !== want) return;   // a newer pick won
  if (r.code !== 200){ box.innerHTML = `<p class="small no">${esc(r.data.error || "HTTP " + r.code)}</p>`; return; }
  const I = DB.imp = r.data;
  dbSteps(2);
  dbTeachReady();
  if (I.noop){ box.innerHTML = `<p class="db-headline">That is today's rule — change a value to make it a change.</p>`; return; }
  const H = I.holdout, nCh = I.exam.filter(e => e.changed.length).length;
  box.innerHTML = `<p class="db-headline">New rule: “${esc(I.sentence)}”</p>
    <div class="db-impact">
      <div class="db-stat stat card"><div class="big stat__value">${H.changed}<small> / ${H.total}</small></div>
        <div class="lbl stat__label">test ${dbNouns()} this rule changes (${(100 * H.changed / H.total).toFixed(0)}%)</div></div>
      <div><div class="lbl">decisions it changes</div>${Object.entries(H.by_decision).map(([q, k]) =>
        `<span class="db-chip chip chip--info">${esc(dbTitle(q))} × ${k}</span>`).join("")}
        <p class="small">The lesson: ${I.corpus.changed.toLocaleString("en-US")} of ${I.corpus.total.toLocaleString("en-US")} past ${dbNouns()}
        re-decided by the rulebook. Re-teaching uses ${I.teach.changed_rows} of them plus ${I.teach.same_rows} the rule
        leaves alone, to hold the rest of the rulebook in place.</p></div>
    </div>
    <h3>The exam: ${I.exam.length} ${dbNouns()} your model has never seen</h3>
    <p class="small"><b>${nCh}</b> the new rule changes (amber) — today's model still follows the old rule on them —
      and <b>${I.exam.length - nCh}</b> it leaves alone. Click any to try it in step ⑤.</p>
    <div class="db-grid">${I.exam.map((e, i) => dbTileHTML(e, i, null)).join("")}</div>`;
  dbWireTiles(box, I.exam);
}
function dbTileHTML(e, i, after){
  const before = e.before || {}, qs = e.changed, n = Object.keys(e.new_gold).length;
  const right = (m, gold) => Object.keys(gold).filter(q => m && m[q] === gold[q]).length;
  // out of the box (untrained Laya), scored against the rulebook the trained model is shown against
  const zeroLine = e.zero ? `<div class="small db-zero">out of the box: ${right(e.zero, after ? e.new_gold : e.old_gold)}/${n} right</div>` : "";
  let cls = "db-tile card", body;
  if (qs.length){
    cls += after ? (qs.every(q => after[q] === e.new_gold[q]) ? " win card--success" : " miss card--danger") : " chg card--warning";
    body = qs.map(q => {
      const b = before[q], nv = e.new_gold[q], old = e.old_gold[q];
      if (!after)
        return `<div><span class="q">${esc(dbTitle(q))}</span> ${esc(dbVal(q, old))} → <b>${esc(dbVal(q, nv))}</b></div>
          <div class="small">today's model: ${esc(dbVal(q, b))} ${b === nv ? "✓" : b === old ? "· old rule" : "✗"}</div>`;
      const a = after[q];
      return `<div><span class="q">${esc(dbTitle(q))}</span> <s>${esc(dbVal(q, b))}</s> → <b>${esc(dbVal(q, a))}</b>
        ${a === nv ? dbMark(true) : `<span class="no">✗ rule: ${esc(dbVal(q, nv))}</span>`}</div>`;
    }).join("") + zeroLine;
  } else if (after){
    const k = right(after, e.new_gold); cls += k === n ? " kept card--success" : " miss card--danger";
    const wrong = Object.keys(e.new_gold).filter(q => after[q] !== e.new_gold[q]);
    body = `<div class="small">no change under the new rule · re-taught ${k}/${n} right ${dbMark(k === n)}</div>` +
      wrong.map(q => `<div class="small no">${esc(dbTitle(q))}: ${esc(dbVal(q, after[q]))} (rule: ${esc(dbVal(q, e.new_gold[q]))})</div>`).join("") + zeroLine;
  } else {
    body = `<div class="small">no change under the new rule · today's model ${right(before, e.old_gold)}/${n} right</div>` + zeroLine;
  }
  return `<div class="${cls}" data-i="${i}" role="button" tabindex="0" aria-label="try ${esc(e.id)} below">
    <div class="id">${esc(e.id.toUpperCase())}</div><div class="facts">${esc(dbFacts(e.state))}</div>${body}</div>`;
}
function dbWireTiles(root, exam){
  root.querySelectorAll(".db-tile").forEach(t => {
    const go = () => dbTry(exam[Number(t.dataset.i)].state, true);
    t.onclick = go;
    t.onkeydown = (ev) => { if (ev.key === "Enter" || ev.key === " "){ ev.preventDefault(); go(); } };
  });
}

// ---- act 3: re-teach ----
function dbAct3HTML(){
  return `<section class="db-act section" id="dbAct3"><header class="section-head"><p class="kicker">Step 3 · Re-teach</p>
    <h2>Teach your model the new rule — live, on this machine</h2></header>
    <div class="db-teachrow">
      <button class="db-go btn btn--success" id="dbTeach" disabled>Re-teach (${TEACH_ETA}) — presenter</button>
      <span class="small" id="dbTeachNote">pick a rule change first</span></div>
    <div id="dbRun" hidden>
      <div class="db-phases">
        <div class="db-phase card card--muted" data-ph="prep"><b>1 · Prepare</b><br>relabel past ${dbNouns()} under the new rule, free the GPU</div>
        <div class="db-phase card card--muted" data-ph="learn"><b>2 · Learn</b><br><span id="dbLearn">fine-tune your model</span><div class="progress" role="progressbar" aria-label="Learning progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i class="progress__bar" id="dbBar" style="width:0%"></i></div></div>
        <div class="db-phase card card--muted" data-ph="exam"><b>3 · Exam</b><br>the unseen ${dbNouns()}</div>
      </div>
      <div class="db-teachrow"><span class="stat"><span class="db-clock stat__value" id="dbClock">0:00</span><span class="stat__label"> elapsed</span></span><span class="small" id="dbMsg"></span></div>
      <div class="db-ask callout callout--warning"><b>While it learns, ask the room:</b> the last time your team changed a rule like this,
        how long did it take to reach the system that makes the decisions — and who had to be involved?</div>
    </div>
    <p class="small status-line" id="dbTeachErr" role="status"></p></section>`;
}
function dbTeachReady(){
  const btn = $("dbTeach"), note = $("dbTeachNote");
  if (!btn || DB.running) return;
  const ok = DB.imp && !DB.imp.noop && DB.s.prod_ready;
  btn.disabled = !ok;
  note.textContent = !DB.s.prod_ready ? "no production model on this host"
    : !DB.imp ? "pick a rule change first"
    : DB.imp.noop ? "that is today's rule"
    : `${DB.imp.teach.changed_rows + DB.imp.teach.same_rows} relabeled ${dbNouns()}, ${DB.imp.teach.epochs} pass${DB.imp.teach.epochs === 1 ? "" : "es"}, starting from your model`;
}
function dbFailText(d){
  const k = d.error_kind;
  if (k === "token") return "Wrong or missing studio token — press Re-teach and enter it again.";
  if (k === "throttled") return "Too many token attempts — wait a minute, then retry.";
  if (k === "busy") return "A re-teach is already running — this page follows it.";
  if (k === "lost") return "The studio restarted during the run — press Re-teach again.";
  return d.error || ("couldn't re-teach (" + (k || "unknown error") + ")");
}
async function dbTeach(){
  const btn = $("dbTeach"), err = $("dbTeachErr");
  if (!DB.imp || DB.imp.noop) return;
  const tok = sessionStorage.getItem("studioToken") || prompt("Studio token (presenter only):") || "";
  btn.disabled = true; err.textContent = "";
  let r;
  try { r = await studioCall("/train", {domain: DB.domain, policy: DB.pol}, tok); }
  catch (e){ err.textContent = "Network error — the studio is unreachable; press Re-teach to retry."; btn.disabled = false; return; }
  if (r.data.error_kind === "token") sessionStorage.removeItem("studioToken");
  else sessionStorage.setItem("studioToken", tok);
  if (r.code !== 200){
    err.innerHTML = `<span class="no">${esc(dbFailText(r.data))}</span>`;
    if (r.data.error_kind !== "busy") btn.disabled = false;
    return;
  }
  $("dbAct4").hidden = true;                 // the previous result is about to be replaced
  dbRunning({state:"training", elapsed_s:0, progress:null, messages:[], sentence: DB.imp && DB.imp.sentence});
}
function dbRunning(s){
  DB.running = true;
  $("dbRun").hidden = false;
  $("dbTeach").disabled = true;
  $("dbTeachNote").textContent = s.sentence ? `teaching: “${s.sentence}”` : "teaching…";
  dbSteps(3);
  dbStateRender();
  const p = s.progress, learning = !!(p && p.epochs);
  const ph = s.state === "evaluating" ? "exam" : learning ? "learn" : "prep";
  const order = ["prep", "learn", "exam"];
  document.querySelectorAll("#dbRun .db-phase").forEach(d => {
    const k = order.indexOf(d.dataset.ph), cur = order.indexOf(ph);
    d.classList.toggle("now", k === cur); d.classList.toggle("done", k < cur);
    if (k === cur) d.setAttribute("aria-current", "step"); else d.removeAttribute("aria-current");
  });
  if (p && p.epochs){
    const frac = Math.min(1, (p.epoch - 1 + (p.steps ? (p.step || 0) / p.steps : 0)) / p.epochs);
    $("dbBar").style.width = (100 * frac).toFixed(1) + "%";
    $("dbBar").parentElement.setAttribute("aria-valuenow", (100 * frac).toFixed(1));
    $("dbLearn").textContent = p.step > 0 ? `pass ${p.epoch} of ${p.epochs}` : "loading your model onto the GPU…";
  }
  if (ph === "exam"){
    $("dbBar").style.width = "100%";
    $("dbBar").parentElement.setAttribute("aria-valuenow", "100");
  }
  const last = (s.messages || []).slice(-1)[0] || "";
  const items = /^train items (\d+), calibration items (\d+)/.exec(last);
  $("dbMsg").textContent = items
    ? `learning from ${Number(items[1]).toLocaleString("en-US")} decisions; ${items[2]} held back to calibrate confidence`
    : /^epoch /.test(last) ? "" : last;
  DB.clock = {base: s.elapsed_s || 0, at: Date.now()};
  if (!DB_CLOCK) DB_CLOCK = setInterval(() => {
    if (!DB || !DB.running || !DB.clock || !$("dbClock")) return;
    $("dbClock").textContent = mmss(DB.clock.base + (Date.now() - DB.clock.at) / 1000);
  }, 250);
}
function dbRunEnd(s){
  DB.running = false;
  if ($("dbRun")) $("dbRun").hidden = true;
  if (s && s.state === "failed") $("dbTeachErr").innerHTML = `<span class="no">${esc(dbFailText(s))}</span>`;
  dbTeachReady();
}

// ---- act 4: what changed ----
function dbShowResult(res, animate){
  DB.result = res;
  const sec = $("dbAct4"), ex = res.exam, S = res.summary;
  const chRows = ex.filter(e => e.changed.length), sameRows = ex.filter(e => !e.changed.length);
  const follows = (e, m) => e.changed.every(q => m && m[q] === e.new_gold[q]);
  const allRight = (e, m) => Object.keys(e.new_gold).every(q => m && m[q] === e.new_gold[q]);
  const winA = chRows.filter(e => follows(e, e.after)).length, winB = chRows.filter(e => follows(e, e.before)).length;
  const keepA = sameRows.filter(e => allRight(e, e.after)).length, keepB = sameRows.filter(e => allRight(e, e.before)).length;
  const f = (x) => `${x[0]}/${x[1]}`;
  sec.hidden = false;
  sec.innerHTML = `<header class="section-head"><p class="kicker">Step 4 · What changed</p>
    <h2>What changed</h2>
    <p class="db-headline">Re-taught in ${Math.round(res.timing.total_s)} s. On the ${chRows.length} unseen ${dbNouns()} the new
      rule changes, your model now follows it on <span class="ok">${winA}</span> (before: ${winB}). On the ${sameRows.length}
      it leaves alone, ${keepA} are still fully right (before: ${keepB}).</p>
    <p class="small">Rule taught: “${esc(res.sentence)}” · finished ${esc(res.finished || "")}</p></header>
    <div class="db-res">
      <div class="db-stat stat card"><div class="big stat__value">${f(S.before.changed)} → ${f(S.after.changed)}</div>
        <div class="lbl stat__label">decisions the rule changed, right under the new rule</div></div>
      <div class="db-stat stat card"><div class="big stat__value">${f(S.before.kept)} → ${f(S.after.kept)}</div>
        <div class="lbl stat__label">decisions the rule left alone, still right</div></div>
      <div class="db-stat stat card"><div class="big stat__value">${f(S.before.all7)} → ${f(S.after.all7)}</div>
        <div class="lbl stat__label">${dbNouns()} with all 7 decisions right under the new rulebook</div></div>
      ${S.zero ? `<div class="db-stat stat card card--muted"><div class="big stat__value">${f(S.zero.all7)}</div>
        <div class="lbl stat__label">out of the box (Laya, no training) on the same exam — ${f(S.zero.changed)} changed and
        ${f(S.zero.kept)} untouched decisions right</div></div>` : ""}
    </div>
    <div class="db-grid">${ex.map((e, i) => dbTileHTML(e, i, e.after)).join("")}</div>
    <p class="small">Green: follows the new rule (or, where the rule changes nothing, still fully right). Red: wrong.
      Click any ${dbNoun()} to put the models side by side.</p>`;
  dbWireTiles(sec, ex);
  dbSteps(4);
  dbStateRender();
  dbRenderMutators();
  dbFine();
  const pre = document.querySelector("#dbAct5 .db-sub");
  if (pre) pre.innerHTML = dbAct5Sub();
  if (animate){
    sec.querySelectorAll(".db-tile").forEach((t, i) => setTimeout(() => t.classList.add("flip"), 90 * i));
    dbScroll(sec);
    const ch = ex.find(e => e.changed.length);
    if (ch) dbTry(ch.state, false);
  }
}

// ---- act 5: try to break it ----
function dbAct5Sub(){
  return DB.result
    ? `Three models answer the same text: Laya out of the box (no training), your model (trained, old rule) and the re-taught model (“${esc(DB.result.sentence)}”). The rulebook column is the referee.`
    : `Two models answer the same text: Laya out of the box (no training) and your model (trained on today's rulebook). Re-teach a rule change and the new model joins the table.`;
}
function dbAct5HTML(){
  return `<section class="db-act section" id="dbAct5"><header class="section-head"><p class="kicker">Step 5 · Try to break it</p>
    <h2>Hand it any ${dbNoun()} — untrained, trained and re-taught answer side by side</h2>
    <p class="small db-sub">${dbAct5Sub()}</p>
    <p class="small">Open to everyone: open this page on your phone, edit a ${dbNoun()}, press <b>Ask the models</b>.</p></header>
    <div class="db-try">
      <div>
        <textarea id="dbText" rows="7" aria-label="${dbNoun()} text"></textarea>
        <div class="db-mut" id="dbMut"></div>
        <button class="btn btn--primary" id="dbAskBtn">Ask the models</button>
      </div>
      <div id="dbAnswer"><p class="small">Pick a ${dbNoun()} from the exam, use “try it yourself” above, or edit this one — then ask.</p></div>
    </div></section>`;
}
function dbRenderMutators(){
  const box = $("dbMut"); if (!box) return;
  const pol = (DB.result && DB.result.policy) || DB.pol;
  const kind = pol && pol.kind, P = (pol && pol.params) || {};
  const tier = kind === "vip" ? P.tier : "Premium";
  const cats = Object.keys(DB.s.text.things);
  const catSel = kind === "reassign" ? P.cat : cats[0];
  box.innerHTML = `
    <button type="button" data-m="tier" class="chip${kind === "vip" ? " hint chip--info" : ""}">Make it ${esc(tier)}</button>
    <button type="button" data-m="nodocs" class="chip${kind === "risk" ? " hint chip--info" : ""}">Remove the evidence</button>
    <button type="button" class="chip" data-m="big">USD 22,000</button>
    <button type="button" class="chip" data-m="fresh">Started 9 days ago</button>
    <span class="db-mut-category"><button type="button" class="chip${kind === "reassign" ? " hint chip--info" : ""}" data-m="cat">Make it</button>
      <select id="dbCatSel" aria-label="category">${cats.map(c => `<option value="${esc(c)}"${c === catSel ? " selected" : ""}>${esc(humanize(c))}</option>`).join("")}</select></span>
    ${DB.s.probes.length ? `<button type="button" class="chip" data-m="reword">Reword it (hand-written)</button>` : ""}
    <button type="button" class="chip" data-m="reset">↺ original</button>`;
  box.querySelectorAll("button[data-m]").forEach(b => b.onclick = () => {
    const ta = $("dbText"); let t = ta.value;
    const m = b.dataset.m;
    if (m === "tier") t = dbSetGroup(t, "tier", tier);
    else if (m === "nodocs") t = dbNoDocs(t);
    else if (m === "big") t = t.replace(/USD [\d,]+/, "USD 22,000");
    else if (m === "fresh") t = dbSetGroup(t, "start", dbDaysBefore(DB.s.text.today, 9));
    else if (m === "cat") t = dbMakeCat(t, $("dbCatSel").value);
    else if (m === "reword"){ const pr = DB.s.probes[(DB.probeIdx = (DB.probeIdx || 0) + 1) % DB.s.probes.length]; t = pr.state; }
    else if (m === "reset") t = DB.tryOrig || t;
    ta.value = t;
    dbAsk();
  });
}
function dbTry(text, scroll){
  DB.tryOrig = text;
  $("dbText").value = text;
  if (scroll) dbScroll($("dbAct5"));
  dbAsk();
}
async function dbAsk(){
  const box = $("dbAnswer"), text = $("dbText").value.trim(), domain = DB.domain;
  if (!text){ box.innerHTML = `<p class="small">Type or paste a ${dbNoun()} first.</p>`; return; }
  box.innerHTML = `<p class="thinking">the models are reading it…</p>`;
  let r;
  try { r = await studioCall("/compare", {domain, state: text}); }
  catch (e){ box.innerHTML = `<p class="small no">network error — press Ask again</p>`; return; }
  if (!DB || DB.domain !== domain || $("dbText").value.trim() !== text) return;   // superseded
  const d = r.data;
  if (r.code !== 200){
    box.innerHTML = `<p class="small no">${esc(d.error_kind === "busy" ? (d.error || "busy") + "." : d.error || "HTTP " + r.code)}</p>`;
    return;
  }
  if (DB.result) dbSteps(5);
  const qids = dbQids(), A = d.after, RO = d.rules_old, RN = d.rules_new || d.rules_old;
  const v = (m, q) => m && m.answers[q] ? m.answers[q].v : undefined;
  // A rulebook that can't read part of the text silently misses facts elsewhere too (an unread date
  // drops a warning sign), so a partial read referees nothing: no ✓/✗, no "rule applies" claim.
  const unread = qids.filter(q => RN[q].v === "unparsed" || RO[q].v === "unparsed");
  const partial = unread.length > 0;
  const touched = d.rules_new && !partial ? qids.filter(q => RN[q].v !== RO[q].v) : [];
  const judge = (m, R, q) => partial ? "" : dbMark(v(m, q) === R[q].v);
  const same = A ? qids.filter(q => v(A, q) === v(d.before, q)).length : 0;
  const Z = d.zero;   // out of the box: the same Laya, untrained, asked with today's question text
  const score = (m, R) => qids.filter(q => v(m, q) === R[q].v).length;
  const board = partial ? "" : `<div class="db-board">
      ${Z ? `<span class="db-chip chip">out of the box <b class="${score(Z, RO) === qids.length ? "ok" : "no"}">${score(Z, RO)}/${qids.length}</b></span>` : ""}
      <span class="db-chip chip">your model <b class="${score(d.before, RO) === qids.length ? "ok" : "no"}">${score(d.before, RO)}/${qids.length}</b> under today's rule</span>
      ${A ? `<span class="db-chip chip">re-taught <b class="${score(A, RN) === qids.length ? "ok" : "no"}">${score(A, RN)}/${qids.length}</b> under the new rule</span>` : ""}</div>`;
  let lead;
  if (partial)
    lead = `<b>The rulebook can't read this wording</b> (${unread.length} of ${qids.length} decisions unreadable), so it can't
      referee — rewording is exactly what breaks rules engines. The models still answer${A ? `; your model and the re-taught one agree on ${same} of ${qids.length}` : ""}. Judge them yourself.`;
  else if (!A) lead = `Your model agrees with today's rulebook on ${score(d.before, RO)} of ${qids.length} decisions${Z ? `; the same model out of the box, on ${score(Z, RO)}` : ""}.
    <span class="small">“Your model” was trained before this demo on 2,000 past ${dbNouns()} the rulebook had decided — so
    on familiar wording it matches the rulebook; on reworded ${dbNouns()} the rulebook can't read, it still answers.</span>`;
  else if (touched.length){
    const ok = touched.every(q => v(A, q) === RN[q].v);
    lead = `<b>The new rule applies here</b> (${touched.map(q => esc(dbTitle(q)) + ": " + esc(dbVal(q, RO[q].v)) + " → " + esc(dbVal(q, RN[q].v))).join("; ")}).
      Your model follows the old rule; the re-taught model ${ok ? `<span class="ok">follows the new one ✓</span>` : `<span class="no">doesn't yet ✗</span>`}.`;
  } else {
    lead = `The new rule doesn't touch this ${dbNoun()}, so your model and the re-taught one <i>should</i> agree — they do on
      ${same} of ${qids.length}. The difference training makes is the out-of-the-box column.`;
  }
  box.innerHTML = `<p>${lead}</p>${board}
    <div class="table-wrap" role="region" aria-label="Model and rulebook comparison" tabindex="0"><table class="table db-dt"><thead><tr><th>decision</th>${Z ? "<th>out of the box<br><span class=\"small\">no training</span></th>" : ""}<th>your model<br><span class="small">pre-trained before this demo</span></th>${A ? "<th>re-taught<br><span class=\"small\">new rule, this session</span></th>" : ""}<th>rulebook${A ? " (new)" : ""}${partial ? " — partial read" : ""}</th></tr></thead><tbody>${
      qids.map(q => `<tr class="${touched.includes(q) ? "diff is-changed" : ""}"><td>${esc(dbTitle(q))}</td>
        ${Z ? `<td>${judge(Z, RO, q)} ${esc(dbVal(q, v(Z, q)))}</td>` : ""}
        <td>${judge(d.before, RO, q)} ${esc(dbVal(q, v(d.before, q)))}</td>
        ${A ? `<td>${judge(A, RN, q)} <b>${esc(dbVal(q, v(A, q)))}</b></td>` : ""}
        <td${partial ? ` class="small"` : ""}>${esc(dbVal(q, RN[q].v))}${touched.includes(q) ? ` <span class="db-chip chip chip--warning">was ${esc(dbVal(q, RO[q].v))}</span>` : ""}
          <div class="small">${esc((RN[q].why || []).join("; "))}</div></td></tr>`).join("")}</tbody></table></div>
    <p class="lat">${Z ? `out of the box ${Z.ms} ms · ` : `<span class="no">out-of-the-box model unavailable</span> · `}your model ${d.before.ms} ms${A ? ` · re-taught ${A.ms} ms` : ""} · on this machine's GPU, nothing leaves it.
      ${partial ? "" : `✓/✗ = agrees with the rulebook each model was asked under (today's${A ? " / new for the re-taught one" : ""}).`}</p>`;
}

// ---- fine print ----
function dbFineHTML(){
  return `<details class="db-fine disclosure" id="dbFine"><summary>How this was built and measured</summary><div id="dbFineBody"></div></details>`;
}
function dbFine(){
  const box = $("dbFineBody"); if (!box) return;
  const nouns = dbNouns(), res = DB.result, M = DB_MEASURED[DB.domain] || {};
  const rows = Object.values(M).map(m => `<tr><td>${esc(m.rule)}</td><td>${m.changed_before} → <b>${m.changed_after}</b></td>
    <td>${m.kept_after}</td><td>${m.all7_before} → ${m.all7_after}</td><td>${m.train_s}</td></tr>`).join("");
  box.innerHTML = `<ul class="small">
    <li><b>Data.</b> A seeded synthetic corpus per business: 2,000 training and ${DB.s.baseline.n} sealed test ${nouns}. Every answer
      comes from the written rulebook, and the rules engine re-derives all of them from the text alone.</li>
    <li><b>Your model.</b> Laya (421M parameters, Apache-2.0) fine-tuned once on the 2,000 training ${nouns} — 3 passes,
      ${esc(DB_PROD_NOTE)}. The out-of-the-box numbers are the same Laya with no training.</li>
    <li><b>Re-teach.</b> Starts from your model, not from scratch. The rulebook re-decides past ${nouns} under the new rule;
      the model trains on ${DB.imp && !DB.imp.noop ? DB.imp.teach.changed_rows + " it changes and " + DB.imp.teach.same_rows + " it doesn't" : "300 it changes and 300 it doesn't"},
      with the new rule also written into the question text.${res ? ` Last run: prepare ${res.timing.prepare_s} s · learn ${res.timing.train_s} s ·
      exam ${res.timing.evaluate_s} s · total ${res.timing.total_s} s (${res.config.epochs} pass${res.config.epochs === 1 ? "" : "es"}, micro-batch ${res.config.micro_batch}; log ${esc(res.config.log)}).` : ""}</li>
    <li><b>Limits.</b> All ${nouns} come from one generator: the exam is unseen but same-format. Free rewording is the hard case
      — try <i>Reword it</i>.${DB_PROBES[DB.domain] ? ` Measured on the 3 hand-reworded ${nouns}: your model gets
      ${DB_PROBES[DB.domain].all7} fully right (${DB_PROBES[DB.domain].decisions} decisions); the rulebook can't read
      ${DB_PROBES[DB.domain].unread} decisions at all.` : ""} Confidences after fine-tuning are sharp; read them as decisions, not odds.</li></ul>
    ${rows ? `<h3>Measured offline on all ${DB.s.baseline.n} test ${nouns} (one run per rule; live runs vary)</h3>
      <div class="table-wrap" role="region" aria-label="Offline measured results" tabindex="0"><table class="table db-dt"><thead><tr><th>rule change</th><th>changed decisions right</th><th>untouched decisions right</th>
      <th>all 7 right</th><th>learn s</th></tr></thead><tbody>${rows}</tbody></table></div>` : ""}`;
}

// ---- live status: presenter and audience follow the same run ----
function dbOnStatus(s){
  const running = s.state === "training" || s.state === "evaluating";
  const live = $("dbLive");
  if (live){
    const other = running && (!DB || s.domain !== DB.domain);
    live.innerHTML = other ? `<div class="db-live callout callout--warning">Live now: re-teaching
      <b>${esc((DOM_META[s.domain] || {}).name || humanize(s.domain || ""))}</b>${s.sentence ? ` — “${esc(s.sentence)}”` : ""}
      <button type="button" class="btn btn--secondary btn--sm" id="dbFollow">follow it</button></div>` : "";
    if (other) $("dbFollow").onclick = () => dbPick(s.domain);
  }
  if (s.taught){ DB_TAUGHT = s.taught; dbBadges(); }
  if (!DB || !DB.s) return;
  if (running && s.domain === DB.domain){
    if (s.policy && JSON.stringify(s.policy) !== JSON.stringify(DB.pol)){   // a teach started elsewhere: show its rule
      DB.pol = {kind: s.policy.kind, params: {...s.policy.params}};
      document.querySelector("#dbAct2 .db-pol").innerHTML = DB.s.presets.map(dbCardHTML).join("");
      dbWireCards();
      dbRenderMutators();
      dbImpact();
    }
    if (!DB.running) $("dbAct4").hidden = true;   // the previous result is about to be replaced
    dbRunning(s);
    return;
  }
  if (DB.running){                               // this business's run just ended
    dbRunEnd(s);
    if (s.state === "done" && s.result && s.domain === DB.domain) dbShowResult(s.result, true);
    else dbStateRender();
    return;
  }
  // a reset (or a run this page missed) changed which model is active: reload what is now true
  if (s.taught && (s.taught[DB.domain] || null) !== (DB.result ? DB.result.finished : null)) dbPick(DB.domain);
}
function dbWatch(){
  if (DB_WATCH) return;
  DB_WATCH = setInterval(async () => {
    if (MODE !== "domain") return;
    try { const r = await studioCall("/status"); if (r.code === 200) dbOnStatus(r.data); } catch (e) { /* blip: keep polling */ }
  }, 2000);
}

async function dbPick(name){
  const el = $("domainfloor");
  DB = {domain: name, s: null, pol: null, imp: null, result: null, showIdx: 0, running: false};
  try { history.replaceState({mode:"domain"}, "", "?mode=domain&d=" + encodeURIComponent(name)); } catch (e) { }
  el.innerHTML = `<div id="dbLive"></div>` + dbPickerHTML() + `<p class="small thinking">loading ${esc((DOM_META[name] || {}).name || name)}…</p>`;
  el.querySelectorAll(".db-dom").forEach(b => b.onclick = () => dbPick(b.dataset.dom));
  let r;
  try { r = await studioCall("/session", {domain: name}); }
  catch (e){ r = {code: 0, data: {error: String(e)}}; }
  if (!DB || DB.domain !== name) return;
  if (r.code === 503 && r.data.error_kind === "warming_up"){
    el.insertAdjacentHTML("beforeend", `<p class="small">${esc(r.data.error)}</p>`);
    setTimeout(() => { if (DB && DB.domain === name && !DB.s) dbPick(name); }, 4000);
    return;
  }
  if (r.code !== 200){
    el.insertAdjacentHTML("beforeend", `<p class="small no">couldn't load this business (${esc(r.data.error || "HTTP " + r.code)}).</p>`);
    return;
  }
  DB.s = r.data;
  const T = DB.s.taught;
  let st = null;
  try { const s = await studioCall("/status"); if (s.code === 200) st = s.data; } catch (e) { }
  if (!DB || DB.domain !== name) return;
  const runHere = st && (st.state === "training" || st.state === "evaluating") && st.domain === name && st.policy;
  if (runHere) DB.pol = {kind: st.policy.kind, params: {...st.policy.params}};
  else if (T) DB.pol = {kind: T.policy.kind, params: {...T.policy.params}};
  dbRender();
  if (DB.pol) dbImpact();
  if (T && !runHere) dbShowResult(T, false);
  dbFine();
  const first = T && !runHere ? (T.exam.find(e => e.changed.length) || T.exam[0]).state : (DB.s.showcase[0] || {}).state;
  if (first){ DB.tryOrig = first; $("dbText").value = first; }
  if (st) dbOnStatus(st);
}

async function initDomain(){
  const el = $("domainfloor");
  el.hidden = false;
  dbWatch();
  if (DOMS) return;
  el.innerHTML = `<p class="small">loading…</p>`;
  try {
    const r = await studioCall("/domains");
    if (r.code !== 200) throw new Error("HTTP " + r.code);
    DOMS = r.data.domains;
    for (const [k, v] of Object.entries(DOMS)) DB_TAUGHT[k] = v.taught ? v.taught.finished : null;
  } catch (e) {
    el.innerHTML = `<div class="db-act"><p>The studio service is unreachable (${esc(String(e))}). It runs on localhost
      :8903 behind the console's /studio proxy.</p></div>`;
    return;
  }
  let s = null;
  try { const r = await studioCall("/status"); if (r.code === 200) s = r.data; } catch (e) { }
  const want = QP.get("d");
  if (s && (s.state === "training" || s.state === "evaluating") && DOMS[s.domain]) return dbPick(s.domain);
  if (want && DOMS[want]) return dbPick(want);
  el.innerHTML = `<div id="dbLive"></div><h2>Pick a business</h2>` + dbPickerHTML() +
    `<p class="small">Each one runs on a written rulebook — seven decisions per case, 2,000 past cases to learn from,
      500 sealed ones to test on. The badge on each card says whether a re-taught model is active.
      <button type="button" class="btn btn--secondary btn--sm" id="dbResetAll">↺ Reset every business to a fresh start — presenter</button></p>`;
  el.querySelectorAll(".db-dom").forEach(b => b.onclick = () => dbPick(b.dataset.dom));
  $("dbResetAll").onclick = () => dbReset("all");
}

