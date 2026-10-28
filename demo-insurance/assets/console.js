function verdictFor(qid, ans, gold){
  if (!gold || !(qid in gold)) return {cls:"v-na", txt:"no rule answer"};
  const g = gold[qid];
  let ok;
  if (ans.choice !== undefined) ok = ans.choice === g;
  else if (ans.noul !== undefined) ok = (ans.noul >= 0.5) === !!g;
  else if (ans.score !== undefined) ok = scoreEq(ans.score, g);
  else return {cls:"v-na", txt:"—"};
  return ok ? {cls:"v-ok", txt:"✓ correct"} : {cls:"v-bad", txt:"✗ wrong"};
}
function allCorrect(answers, gold){
  return Object.keys(gold).every(q => {
    const a = answers[q]; if (!a) return false;
    if (a.noul !== undefined) return (a.noul >= 0.5) === !!gold[q];
    if (a.choice !== undefined) return a.choice === gold[q];
    if (a.score !== undefined) return scoreEq(a.score, gold[q]);
    return false;
  });
}

function barsHTML(ans){
  const probs = ans.probabilities || {};
  const entries = Object.entries(probs).sort((a,b)=>b[1]-a[1]);
  let html = "";
  for (const [k,v] of entries.slice(0,8)){
    html += `<div class="brow${entries[0][0]===k?" top":""}"><span class="k" title="${esc(k)}">${esc(humanize(k))}</span>` +
            `<span class="track progress" role="progressbar" aria-label="${esc(humanize(k))}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.max(0, Math.min(100, 100*v))}" aria-valuetext="${fmtP(v)}"><span class="fill progress__bar" style="width:${Math.max(0, Math.min(100, 100*v))}%"></span></span>` +
            `<span class="p">${fmtP(v)}</span></div>`;
  }
  return html;
}

function answerText(a){   // display-only; raw values stay in title tooltips
  if (a.choice !== undefined) return {txt:esc(humanize(a.choice)), title:esc(String(a.choice))};
  if (a.noul !== undefined) return {txt:a.noul>=0.5?"YES":"NO", title:""};
  if (a.score !== undefined){
    const raw = (typeof a.score === "number") ? a.score : null;
    return {txt:`level ${raw===null?esc(String(a.score)):Math.round(raw)}`, title:raw===null?"":"raw "+raw};
  }
  return {txt:"—", title:""};
}

function updateStory(){
  document.querySelectorAll("#storyStrip [data-step]").forEach(el => {
    const active = el.dataset.step === MODE;
    el.classList.toggle("current", active);
    el.classList.toggle("done", el.dataset.step === "pick" ? !!LAST : STORY_RUNS.has(el.dataset.step));
    if (active) el.setAttribute("aria-current", "step"); else el.removeAttribute("aria-current");
  });
}

// Compare the decisions, not the confidence attached to them.
function sameAnswer(a, b){
  if (!a || !b) return false;
  if (a.choice !== undefined && b.choice !== undefined) return a.choice === b.choice;
  if (a.noul !== undefined && b.noul !== undefined) return (a.noul >= .5) === (b.noul >= .5);
  if (a.score !== undefined && b.score !== undefined) return scoreEq(a.score, b.score);
  return false;
}

function renderDecisionTable(run){
  const el = $("decisions"), engines = MODE_ENGINES[MODE];
  if (!engines.length) return;
  if (!run){ el.innerHTML = `<p class="empty-state">Pick a claim to see the seven decisions.</p>`; return; }
  if (run.pending){ el.innerHTML = `<p class="thinking">Running the same claim across the engines…</p><div class="decision-loading" aria-hidden="true"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>`; return; }
  const {data, gold, state} = run;
  const stages = STAGES.length ? STAGES : [{stage:"Decisions", questions:Object.keys(QUESTIONS || {})}];
  const qids = stages.flatMap(st => st.questions);
  const before = DAY1_ANSWERS.get(state);
  const scoreFor = key => {
    const d = data[key], answers = d && d.note !== "english-only" && d.answers;
    return gold && answers && qids.length && qids.every(q => answers[q] && q in gold)
      ? qids.filter(q => verdictFor(q, answers[q], gold).cls === "v-ok").length : null;
  };
  let headline = "";
  if (MODE === "after"){
    if (!before) headline = "Run this claim in Day 1 first to see what training changed.";
    else if (data.ft && data.ft.note === "english-only") headline = "The fine-tuned model is English only, so its training changes cannot be compared on this claim.";
    else if (data.ft && data.ft.answers && qids.every(q => before[q] && data.ft.answers[q])){
      const changed = qids.filter(q => !sameAnswer(before[q], data.ft.answers[q]));
      const matched = gold && changed.every(q => q in gold)
        ? ` — ${changed.filter(q => verdictFor(q, data.ft.answers[q], gold).cls === "v-ok").length} now match the claims manual` : "";
      headline = `Training changed ${changed.length} of ${qids.length} decisions on this claim${matched}.`;
    } else headline = "Training changes are unavailable because an engine did not return all decisions.";
  } else if (gold && MODE === "day1"){
    const zero = scoreFor("zero"), dec = scoreFor("dec");
    headline = `Out of the box, Laya gets ${zero === null ? "an unavailable score" : `${zero} of ${qids.length}`}; decider-4b gets ${dec === null ? "an unavailable score" : `${dec} of ${qids.length}`}.`;
  } else if (gold && MODE === "compare"){
    const perfect = engines.filter(k => scoreFor(k) === qids.length).map(k => ENGINES[k].name);
    const unavailable = engines.some(k => scoreFor(k) === null);
    headline = perfect.length ? `${perfect.join(", ")} ${perfect.length === 1 ? "gets" : "get"} ${qids.length}/${qids.length} on this claim${unavailable ? " among engines with complete answers" : ""}.`
      : `No engine with complete answers gets ${qids.length}/${qids.length} on this claim.`;
  }
  let html = `<h2>Seven decisions · one claim</h2>${headline ? `<p class="decision-headline">${esc(headline)}</p>` : ""}<div class="decision-scores">`;
  for (const key of engines){
    const count = scoreFor(key), score = count === null ? "—" : `${count}/${qids.length}`;
    html += `<span class="scell chip">${esc(ENGINES[key].name)}: <b>${score}</b></span>`;
  }
  html += `</div>`;
  if (!gold) html += `<p class="console-note callout callout--info">No manual answer — judge yourself.</p>`;
  if (data.ft && data.ft.note === "english-only" && engines.includes("ft"))
    html += `<p class="note callout callout--warning">Fine-tuned on English claims only. For other languages use out-of-box Laya (100+ languages)${MODE === "after" ? ", shown below each English-only cell" : ""}. The English fine-tune trades away language robustness: on a Spanish claim it scored 1/3 where the untrained base scored 2/3.</p>`;
  html += `<button type="button" class="btn btn--secondary btn--sm" id="decisionDetailsToggle" aria-expanded="${SHOW_DECISION_DETAILS}">${SHOW_DECISION_DETAILS ? "Hide" : "Show"} confidence &amp; probabilities</button>`;
  html += `<div class="tablewrap table-wrap" role="region" aria-label="Decision comparison" tabindex="0"><table class="decision-table table"><thead><tr><th scope="col">Decision</th>` +
    engines.map(k => `<th scope="col">${esc(ENGINES[k].name)}<br><span class="small">${esc(ENGINES[k].sub)}</span></th>`).join("") +
    `<th scope="col">Claims manual</th></tr></thead><tbody>`;
  for (const st of stages){
    html += `<tr class="stage-row"><th colspan="${engines.length+2}" scope="colgroup">${esc(st.stage)}</th></tr>`;
    for (const qid of st.questions){
      const ft = data.ft && data.ft.note !== "english-only" && data.ft.answers && data.ft.answers[qid];
      const old = before && before[qid];
      const changed = MODE === "after" && ft && old && !sameAnswer(ft, old);
      html += `<tr${changed ? ' class="changed is-changed"' : ""}><th scope="row">${esc(QTITLE[qid] || humanize(qid))}</th>`;
      for (const key of engines){
        const d = data[key], a = d && d.answers && d.answers[qid];
        const label = esc(({zero:"Laya out-of-box", ft:"Laya fine-tuned", dec:"decider-4b", rules:"Rules engine"})[key]);
        if (!d){ html += `<td data-label="${label}" class="small">unavailable</td>`; continue; }
        if (key === "ft" && d.note === "english-only"){
          const zero = MODE === "after" && data.zero && data.zero.answers && data.zero.answers[qid];
          const zv = zero && verdictFor(qid, zero, gold);
          html += `<td data-label="${label}" class="small">English only${zero ? `<div>Out-of-box Laya: <strong>${answerText(zero).txt}</strong> ${zv.cls === "v-ok" ? '<span class="verdict chip chip--success" aria-label="correct">✓</span>' : zv.cls === "v-bad" ? '<span class="verdict chip chip--danger" aria-label="incorrect">✗</span>' : ""}</div>` : MODE === "after" ? `<div>Out-of-box Laya unavailable</div>` : ""}</td>`;
          continue;
        }
        if (!a){ html += `<td data-label="${label}" class="small">no answer</td>`; continue; }
        const unparsed = key === "rules" && a.choice === "unparsed";
        const v = verdictFor(qid, a, gold), at = answerText(a);
        const mark = !unparsed && v.cls === "v-ok" ? `<span class="verdict v-ok chip chip--success" aria-label="correct">✓</span>` :
          !unparsed && v.cls === "v-bad" ? `<span class="verdict v-bad chip chip--danger" aria-label="incorrect">✗</span>` : "";
        const conf = a.confidence !== undefined ? a.confidence : (a.noul !== undefined ? Math.max(a.noul, 1-a.noul) : null);
        const bars = barsHTML(a);
        const evidence = key === "rules" && d.evidence && d.evidence[qid];
        const details = (conf !== null || bars || evidence || d.routing_model || d.ft_checkpoint || d.ms !== undefined) ?
          `<div class="decision-detail"${SHOW_DECISION_DETAILS ? "" : " hidden"}>${conf !== null ? `<div>confidence ${fmtP(conf)}</div>` : ""}` +
          `${a.noul !== undefined ? `<div>p(yes) ${fmtP(a.noul)}</div>` : ""}${bars}` +
          `${evidence ? `<div class="ev">${evidence.map(e => esc(e)).join("<br>")}</div>` : ""}` +
          `${d.routing_model ? `<div>via ${esc(d.routing_model)}</div>` : ""}` +
          `${d.ft_checkpoint ? `<div>checkpoint: ${esc(d.ft_checkpoint)}</div>` : ""}` +
          `${d.ms !== undefined ? `<div>${esc(d.ms)} ms</div>` : ""}</div>` : "";
        html += `<td data-label="${label}"><strong>${unparsed ? "can't read" : at.txt}</strong> ${mark}` +
          `${changed && key === "ft" ? `<span class="was">was ${answerText(old).txt}</span>` : ""}${details}</td>`;
      }
      html += `<td data-label="Manual">${gold && qid in gold ? goldDisp(qid, gold[qid]) : `<span class="small">no manual answer</span>`}</td></tr>`;
    }
  }
  el.innerHTML = html + `</tbody></table></div>`;
  $("decisionDetailsToggle").onclick = () => {
    SHOW_DECISION_DETAILS = !SHOW_DECISION_DETAILS;
    $("decisionDetailsToggle").setAttribute("aria-expanded", String(SHOW_DECISION_DETAILS));
    $("decisionDetailsToggle").textContent = `${SHOW_DECISION_DETAILS ? "Hide" : "Show"} confidence & probabilities`;
    el.querySelectorAll(".decision-detail").forEach(detail => { detail.hidden = !SHOW_DECISION_DETAILS; });
  };
}

function showClaim(state, lang){
  // Escape each segment before adding markup, including arbitrary pasted claim text.
  const shortFacts = /\b(?:MOTOR|PROPERTY|HEALTH|TRAVEL)-\d+|\b\d{4}-\d{2}-\d{2}\b|\d{4}年\s*\d{1,2}月\s*\d{1,2}日|\bUSD\s*[\d,]+(?:\.\d+)?|\b[\d,]+\s*(?:USD|米ドル|अमेरिकी डॉलर)/;
  const facts = new RegExp(`(No supporting documents[^.]*\\.|The customer attached[^.]*\\.|고객은[^.]*\\.|お客様は[^。]*。|अस्पताल का[^।]*।|El cliente adjuntó[^.]*\\.|${shortFacts.source})`, "gi");
  const shortFact = new RegExp(`^(?:${shortFacts.source})$`, "i");
  const card = $("claimCard");
  card.innerHTML = state.split(facts).map((part, i) => i % 2 ? `<b${part.length <= 32 && shortFact.test(part) ? ' class="claim-fact--short"' : ""}>${esc(part)}</b>` : esc(part)).join("");
  if (lang) card.lang = lang; else card.removeAttribute("lang");
  card.hidden = false;
}

async function runClaim(state, gold, nonLatin, silent, lang){
  const runId = ++RUN_ID, startedMode = MODE;
  LAST = {state, gold, nonLatin, lang};
  if (startedMode === "day1" || startedMode === "after") STORY_RUNS.add(startedMode);
  $("askedState").textContent = state;
  if (lang) $("askedState").lang = lang; else $("askedState").removeAttribute("lang");
  $("askedSchema").textContent = JSON.stringify(QUESTIONS, null, 1);
  $("inputPrompt").textContent = "";
  $("runBtn").disabled = true;
  showClaim(state, lang);
  updateStory();
  LAST_RUN = {pending:true};
  renderDecisionTable(LAST_RUN);
  const SIG = { signal: AbortSignal.timeout(60000) };
  const post = (url, body) => fetch(url, {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify(body), ...SIG}).then(r => r.json());
  const [lrR, drR, rrR] = await Promise.allSettled([
    post(LAYA + "/predict", {state, questions: QUESTIONS, lang}),
    post(DEC, {state, questions: QUESTIONS}),
    post(LAYA + "/rules", {state, questions: QUESTIONS}),
  ]);
  const okArm = (r, name) => (r.status === "fulfilled" && r.value && !r.value.error && r.value[name]) ? r.value[name] : null;
  const lr = lrR.status === "fulfilled" ? lrR.value : null;
  const data = {
    zero: lr && !lr.error && lr.zero ? {answers: lr.zero.answers, ms: lr.zero.ms, routing_model: lr.zero.routing_model} : null,
    ft:   lr && !lr.error && lr.ft ? {answers: lr.ft.answers, ms: lr.ft.ms, routing_model: lr.ft.routing_model,
                                      ft_checkpoint: lr.ft.ft_checkpoint, note: lr.ft.note} : null,
    dec:  okArm(drR, "decider"),
    rules:(rrR.status === "fulfilled" && rrR.value && !rrR.value.error) ? rrR.value : null,
  };
  if (startedMode === "day1" && data.zero && data.zero.answers)
    DAY1_ANSWERS.set(state, data.zero.answers);
  if (runId !== RUN_ID) return;
  LAST_RUN = {data, gold, state};
  renderDecisionTable(LAST_RUN);
  $("runBtn").disabled = !QUESTIONS;
}

function isNonLatin(s){
  return /[\u3131-\uD79F\u3040-\u30FF\u4E00-\u9FFF\u0900-\u097F\u0600-\u06FF\u0590-\u05FF\u0E00-\u0E7F]/.test(s);
}

function goldDisp(qid, value){
  const type = QUESTIONS && QUESTIONS[qid] && QUESTIONS[qid].type;
  return answerText(type === "noul" ? {noul:Number(value)} :
    type === "score" ? {score:value} : {choice:value}).txt;
}

function presetLabel(p){
  return p.label.replace(/^\s*[\u{1F1E6}-\u{1F1FF}]{2}\s*/u, "");
}

function presetLanguage(p){
  const lang = (p.lang || "").toLowerCase().split("-")[0];
  const fromLabel = {korean:"ko", japanese:"ja", hindi:"hi", spanish:"es"};
  const match = p.label.match(/\b(Korean|Japanese|Hindi|Spanish)\b/i);
  const code = ["ko", "ja", "hi", "es"].includes(lang) ? lang : match && fromLabel[match[1].toLowerCase()];
  return code ? code.toUpperCase() : "";
}

function updatePresetGroups(){
  document.querySelectorAll("#presets .preset-group").forEach(group => {
    const expanded = group.dataset.expanded === "true";
    const buttons = [...group.querySelectorAll(".preset")];
    let hiddenCount = 0;
    buttons.forEach((button, index) => {
      const omitted = index >= 3 && !button.classList.contains("sel");
      if (omitted) hiddenCount++;
      button.hidden = !expanded && omitted;
    });
    const more = group.querySelector(".preset-more");
    more.hidden = expanded ? buttons.length <= 3 : hiddenCount === 0;
    more.textContent = expanded ? "fewer" : `+${hiddenCount} more`;
    more.setAttribute("aria-expanded", String(expanded));
  });
}

function collapseClaimPicker(label){
  $("claimPickerLabel").textContent = `Claim: ${label}`;
  $("claimPicker").hidden = true;
  $("claimPickerSummary").hidden = false;
  $("changeClaimBtn").setAttribute("aria-expanded", "false");
  $("changeClaimBtn").focus({preventScroll:true});
}

$("changeClaimBtn").onclick = () => {
  $("claimPicker").hidden = false;
  $("claimPickerSummary").hidden = true;
  $("changeClaimBtn").setAttribute("aria-expanded", "true");
  const selected = $("presets").querySelector(".preset.sel");
  (selected || $("claimPicker").querySelector("h2")).focus({preventScroll:true});
  if (selected && window.matchMedia("(max-width:760px)").matches){
    const row = selected.parentElement;
    row.scrollLeft += selected.getBoundingClientRect().left - row.getBoundingClientRect().left;
  }
};

function loadPresets(){
  const el = $("presets");
  $("runBtn").disabled = true;
  el.innerHTML = `<p class="small">loading presets…</p><div class="preset-loading" aria-hidden="true"><div class="skeleton"></div><div class="skeleton"></div></div>`;
  fetch(LAYA + "/presets").then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(d => {
    PRESETS = d.presets; QUESTIONS = d.questions; STAGES = d.stages || [];
    const groups = {"Standard":[], "Fraud":[], "Multilingual":[]};
    for (const p of PRESETS){
      if (/FRAUD/i.test(p.label)) groups.Fraud.push(p);
      else if (p.lang || /Korean|Japanese|Hindi|Spanish/.test(p.label)) groups.Multilingual.push(p);
      else groups.Standard.push(p);
    }
    el.innerHTML = "";
    for (const [g, items] of Object.entries(groups)){
      const group = document.createElement("div");
      group.className = "preset-group";
      group.dataset.expanded = "false";
      group.innerHTML = `<h3 class="preset-group__label">${esc(g)}</h3><div class="preset-options-shell"><div class="preset-options"></div></div>`;
      el.appendChild(group);
      for (const p of items){
        const b = document.createElement("button");
        b.type = "button";
        b.className = "preset chip";
        b.dataset.presetIndex = PRESETS.indexOf(p);
        b.setAttribute("aria-pressed", "false");
        const code = presetLanguage(p);
        b.innerHTML = `${code ? `<span class="preset-language chip chip--info">${esc(code)}</span>` : ""}<span ${p.lang ? `lang="${esc(p.lang)}"` : ""}>${esc(presetLabel(p))}</span>`;
        b.onclick = () => selectPreset(p);
        group.querySelector(".preset-options").appendChild(b);
      }
      const more = document.createElement("button");
      more.type = "button";
      more.className = "preset-more chip";
      more.setAttribute("aria-label", `Show more or fewer ${g} claims`);
      more.onclick = () => {
        group.dataset.expanded = String(group.dataset.expanded !== "true");
        updatePresetGroups();
        const selected = group.querySelector(".preset.sel");
        if (group.dataset.expanded === "false" && selected){
          if (more.hidden) selected.focus({preventScroll:true});
          if (window.matchMedia("(max-width:760px)").matches){
            const row = selected.parentElement;
            row.scrollLeft += selected.getBoundingClientRect().left - row.getBoundingClientRect().left;
          }
        }
      };
      group.querySelector(".preset-options").appendChild(more);
    }
    updatePresetGroups();
    $("runBtn").disabled = false;
    $("revealBtn").disabled = !PRESETS.length;
  }).catch(e => {
    el.innerHTML = `<p class="small callout callout--warning">couldn't load presets (${esc(String(e))}).</p>`;
    const b = document.createElement("button");
    b.className = "btn btn--secondary btn--sm"; b.textContent = "Retry"; b.onclick = loadPresets;
    el.appendChild(b);
  });
}

function selectPreset(p){
  document.querySelectorAll(".preset").forEach(b => {
    const selected = Number(b.dataset.presetIndex) === PRESETS.indexOf(p);
    b.classList.toggle("sel", selected);
    b.classList.toggle("chip--selected", selected);
    b.setAttribute("aria-pressed", String(selected));
  });
  updatePresetGroups();
  $("freeText").value = "";
  collapseClaimPicker(presetLabel(p));
  runClaim(p.state, p.gold, isNonLatin(p.state), false, p.lang || null);
}
$("runBtn").onclick = () => {
  const t = $("freeText").value.trim();
  if (!t){ $("inputPrompt").textContent = "Paste a claim before running a decision."; return; }
  document.querySelectorAll(".preset").forEach(b => { b.classList.remove("sel", "chip--selected"); b.setAttribute("aria-pressed", "false"); });
  updatePresetGroups();
  collapseClaimPicker("your pasted claim");
  runClaim(t, null, isNonLatin(t));
};
$("revealBtn").onclick = () => {
  if (LAST) setMode("after", true);
  else if (PRESETS.length){ setMode("after", false); selectPreset(PRESETS[0]); }
};
document.querySelectorAll(".tab").forEach(t => t.onclick = () => setMode(t.dataset.mode, false));

$("etaOut").textContent = TEACH_ETA;


