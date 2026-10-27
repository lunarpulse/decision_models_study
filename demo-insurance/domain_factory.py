"""Domain factory: seeded, rule-verifiable decision corpora for arbitrary business domains.

The insurance demo (gen_corpus.py) stays untouched — its rng stream and byte-output are frozen.
This factory serves NEW domains: each domain is a declarative spec (domains.py) consumed here.
Every domain ships the same 7-question journey archetypes, domain-worded:

  routing (choice) · risk-flag (noul) · urgency (score) · eligibility (choice)
  money-band (choice) · third-party-recovery (noul) · expected-touches (score)

All gold is computed by rules stated verbatim in the question instructions, and every spec
declares renderer/regex pairs for its state fields so a replay validator (validate_corpus.py)
and a spec-driven rules engine (decide(), used as Engine D per domain) can recompute gold from
raw state text alone — the same standard the insurance corpus meets (500/500 replay).

Canonical rng draw order (fixed for all factory domains; each domain has its own seed):
  cat -> thing -> amount -> account_age_days -> docs_ok -> tier -> name
  -> filed_lag -> incident_lag -> [large-amount variant, conditional] -> channel
"""
import json, random, datetime, pathlib, re

FIRST = ["J.", "M.", "A.", "R.", "S.", "K.", "L.", "D.", "P.", "T."]
NAMES = ["Alvarez", "Bennett", "Cho", "Dubois", "Eriksen", "Ferreira", "Gupta", "Haddad", "Ibrahim", "Johnson",
         "Kim", "Larsen", "Martin", "Nakamura", "Okafor", "Park", "Quinn", "Rossi", "Silva", "Tanaka",
         "Ueda", "Vargas", "Wong", "Yoon", "Zhang"]
AMOUNTS = [240, 480, 850, 1200, 1650, 2100, 2800, 3400, 4200, 5100, 6300, 7400, 8800, 9600, 11200, 13400, 15800, 18500, 22000, 26500]
AGE_DAYS = [3, 9, 17, 26, 45, 80, 140, 260, 400, 700]
FILED_LAGS = [0, 1, 2, 4, 7]
INCIDENT_LAGS = [0, 1, 2, 5, 9]
TIERS = ["Basic", "Standard", "Plus", "Premium"]
DOCS_OK_PROB = 0.72
HIGH_VALUE = 8800          # urgency/touches complication threshold
BANDS = [(0, "zero"), (1000, "up_to_1000"), (5000, "1000_to_5000"), (15000, "5000_to_15000")]
BAND_OVER = "over_15000"


def _band(payable):
    if payable == 0:
        return "zero_nothing_payable"
    for hi, name in BANDS:
        if payable <= hi and name != "zero":
            return name if name != "up_to_1000" else "up_to_1000"
    return BAND_OVER


def band_key(payable, zero_key, band_names):
    """Map payable to the domain's band option keys (spec-declared order)."""
    if payable == 0:
        return zero_key
    if payable <= 1000: return band_names[0]
    if payable <= 5000: return band_names[1]
    if payable <= 15000: return band_names[2]
    return band_names[3]


def make_row(spec, rng, i, force=None):
    """One row: state text + rule gold + meta. Draw order is canonical (see module doc)."""
    cat = force["cat"] if force else rng.choice(list(spec["categories"]))
    c = spec["categories"][cat]
    thing = rng.choice(c["things"])
    amount = rng.choice(spec.get("amounts", AMOUNTS))
    age_days = rng.choice(spec.get("age_days", AGE_DAYS))
    docs_ok = rng.random() < spec.get("docs_ok_prob", DOCS_OK_PROB)
    tier = rng.choice(spec.get("tiers", TIERS))
    name = rng.choice(FIRST) + " " + rng.choice(NAMES)

    today = spec.get("today", datetime.date(2026, 10, 8))
    filed = today - datetime.timedelta(days=rng.choice(FILED_LAGS))
    incident = filed - datetime.timedelta(days=rng.choice(INCIDENT_LAGS))
    start = today - datetime.timedelta(days=age_days)

    S = spec["signals"]
    markers = 0
    if not docs_ok: markers += 1
    if age_days <= S["fresh_days"]: markers += 1
    if amount >= S["large_amount"]: markers += 1
    flag = markers >= S.get("flag_markers", 2)

    gold = {}
    Q = spec["questions"]
    gold[Q["archetypes"]["routing"]] = S["flag_unit"] if flag else c["unit"]
    gold[Q["archetypes"]["risk_flag"]] = flag

    urg = spec["urgency"]
    if any(w in thing for w in urg["critical_words"]): u = 3
    elif any(w in thing for w in urg["urgent_words"]): u = 2
    elif amount >= HIGH_VALUE or cat in urg["priority_cats"]: u = 1
    else: u = 0
    u = max(u, urg.get("tier_floor", {}).get(tier, 0))     # policy knob (default: none)
    gold[Q["archetypes"]["urgency"]] = u

    # eligibility (mirrors insurance logic, domain-worded options)
    elig_key = Q["archetypes"]["eligibility"]
    E = spec["eligibility"]
    if incident < start:
        elig = E["not_active_key"]
    elif incident <= start + datetime.timedelta(days=2):
        elig = E["review_key"]
    elif any(k in thing for k in E["excluded_peril_words"]) and tier in E["excluded_tiers"]:
        elig = E["excluded_key"]
    else:
        elig = E["ok_key"]
    gold[elig_key] = elig

    ded = spec["deductibles"][cat]
    payable = 0 if (flag or elig != E["ok_key"]) else max(0, amount - ded)
    gold[Q["archetypes"]["money_band"]] = band_key(
        payable, Q["band_zero_key"], Q["band_keys"])

    gold[Q["archetypes"]["third_party"]] = (
        any(k in thing for k in spec["third_party"]["always_words"]) or
        (any(k in thing for k in spec["third_party"]["with_docs_words"]) and docs_ok))

    complications = (0 if docs_ok else 1) + (1 if amount >= HIGH_VALUE else 0) + \
                    (0 if elig == E["ok_key"] else 1)
    gold[Q["archetypes"]["touches"]] = 3 if flag else min(3, complications)

    doc_phrase = (spec["doc_ok_template"].format(docs=" and ".join(c["docs"]))
                  if docs_ok else spec["doc_missing_phrase"])
    amount_phrase = f"USD {amount:,}"
    if amount >= S["large_amount"] and rng.random() < 0.5:
        amount_phrase = f"USD {amount:,} {S['large_amount_suffix']}"

    state = spec["state_template"].format(
        prefix=spec["id_prefix"], n=90000 + i, name=name, filed=filed.isoformat(),
        channel=rng.choice(spec["channels"]), cat=cat.upper(), ref=5000 + i,
        start=start.isoformat(), thing=thing, incident=incident.isoformat(),
        amount_phrase=amount_phrase, doc_phrase=doc_phrase, tier=tier)

    meta = {"cat": cat, "amount": amount, "age_days": age_days, "docs_ok": docs_ok,
            "flag": flag, "tier": tier, "deductible": ded, "payable": payable,
            "incident_iso": incident.isoformat(), "filed_iso": filed.isoformat(),
            "start_iso": start.isoformat(), "complications": complications,
            "eligibility": elig}
    return {"id": f"{spec['id_prefix'].lower()}-{i:06d}", "state": state,
            "questions": spec["questions"]["defs"], "gold": gold, "meta": meta}


def generate_domain(spec, out_dir):
    import collections
    """Write train/validation/holdout jsonl + demo_presets.json. Deterministic per seed."""
    rng = random.Random(spec["rng_seed"])
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows, seen, i = {}, set(), 0
    target = spec["counts"]["train"] + spec["counts"]["val"] + spec["counts"]["holdout"] + \
             spec["counts"].get("surplus", 980)
    while len(rows) < target:
        r = make_row(spec, rng, i)
        if r["state"] not in seen:
            seen.add(r["state"]); rows[r["id"]] = r
        i += 1
    all_rows = list(rows.values())
    rng.shuffle(all_rows)
    n_tr, n_va = spec["counts"]["train"], spec["counts"]["val"]
    train, validation, holdout = all_rows[:n_tr], all_rows[n_tr:n_tr + n_va], all_rows[n_tr + n_va:n_tr + n_va + spec["counts"]["holdout"]]

    def to_train(r):
        return {"state": r["state"], "questions": r["questions"], "expected": r["gold"]}

    with open(out / "train.jsonl", "w") as f:
        for r in train: f.write(json.dumps(to_train(r)) + "\n")
    with open(out / "validation.jsonl", "w") as f:
        for r in validation: f.write(json.dumps(to_train(r)) + "\n")
    with open(out / "holdout_eval.jsonl", "w") as f:
        for r in holdout: f.write(json.dumps(r) + "\n")

    # curated presets (deterministic forces)
    presets = []
    for k, force in enumerate(spec["preset_forces"]):
        for attempt in range(4000):
            r = make_row(spec, rng, 990000 + k * 100 + attempt, force=force)
            ok = r["meta"]["flag"] == force["want_flag"]
            if force.get("want_urgency") is not None:
                ok = ok and r["gold"][spec["questions"]["archetypes"]["urgency"]] == force["want_urgency"]
            if ok:
                presets.append({"label": force["desc"], "id": r["id"], "state": r["state"],
                                "gold": r["gold"], "meta": r["meta"]})
                break
    pkg = {"domain": spec["name"], "questions": spec["questions"]["defs"],
           "stages": spec["stages"], "presets": presets,
           "paraphrase_probes": spec.get("paraphrase_probes", [])}
    with open(out / "demo_presets.json", "w") as f:
        json.dump(pkg, f, indent=1, ensure_ascii=False)
    ek = spec["questions"]["archetypes"]["eligibility"]
    print(f"[{spec['name']}] eligibility dist", dict(collections.Counter(r["gold"][ek] for r in train)))
    print(f"[{spec['name']}] presets:", [p["label"] for p in presets])


# ---------------- spec-driven rules engine (Engine D for factory domains) ----------------

def parse_state(spec, state):
    p = {}
    R = spec["parsers"]
    if m := re.search(R["ref"], state):
        p["cat"] = m.group(1).lower()
    if m := re.search(R["start"], state):
        p["start"] = datetime.date.fromisoformat(m.group(1))
    if m := re.search(R["incident"], state):
        p["incident"] = datetime.date.fromisoformat(m.group(1))
    if m := re.search(R["amount"], state):
        p["amount"] = int(m.group(1).replace(",", ""))
    if m := re.search(R["tier"], state):
        p["tier"] = m.group(1)
    p["docs_ok"] = spec["doc_missing_marker"] not in state
    return p


def decide(spec, state):
    """Engine D for a factory domain: rules replay from raw text, with evidence."""
    Q = spec["questions"]; A = Q["archetypes"]
    p = parse_state(spec, state)
    answers, evidence = {}, {}
    S = spec["signals"]

    fired = []
    if not p.get("docs_ok"):
        fired.append(spec["evidence"]["no_docs"])
    if p.get("start") and p["start"] >= S["today"] - datetime.timedelta(days=S["fresh_days"]):
        fired.append(spec["evidence"]["fresh"].format(start=p["start"]))
    if p.get("amount", 0) >= S["large_amount"]:
        fired.append(spec["evidence"]["large"].format(amount=p["amount"]))
    need = S.get("flag_markers", 2)
    flag = len(fired) >= need
    answers[A["risk_flag"]] = {"type": "noul", "noul": 1.0 if flag else 0.0}
    evidence[A["risk_flag"]] = fired or [spec["evidence"]["no_markers"]]

    if "cat" not in p:
        answers[A["routing"]] = {"type": "choice", "choice": "unparsed"}
        evidence[A["routing"]] = [spec["evidence"]["no_ref"]]
    elif flag:
        answers[A["routing"]] = {"type": "choice", "choice": S["flag_unit"]}
        evidence[A["routing"]] = [spec["evidence"]["flag_route"].replace("2+", f"{need}+")]
    else:
        # best category by keyword hits, then its unit (a policy may give two categories one unit)
        hits = {k: sum(w in state for w in c["things"]) for k, c in spec["categories"].items()}
        best = max(hits, key=hits.get)
        unit = spec["categories"][best]["unit"] if hits[best] > 0 else "unparsed"
        answers[A["routing"]] = {"type": "choice", "choice": unit}
        evidence[A["routing"]] = [spec["evidence"]["keyword_route"].format(unit=unit)]

    urg = spec["urgency"]
    # urgency needs the thing text: use keyword proximity on the state string
    if any(w in state for w in urg["critical_words"]): u = 3
    elif any(w in state for w in urg["urgent_words"]): u = 2
    elif p.get("amount", 0) >= HIGH_VALUE or (p.get("cat", "") in urg["priority_cats"]): u = 1
    else: u = 0
    floor = urg.get("tier_floor", {}).get(p.get("tier"), 0)    # policy knob (default: none)
    if floor > u:
        u = floor
        evidence_urg = [f"rule level {u} ({p.get('tier')} tier floor)"]
    else:
        evidence_urg = [f"rule level {u}"]
    answers[A["urgency"]] = {"type": "score", "score": u}
    evidence[A["urgency"]] = evidence_urg

    E = spec["eligibility"]
    if "incident" not in p or "start" not in p:
        elig = "unparsed"; ev = [spec["evidence"]["no_dates"]]
    elif p["incident"] < p["start"]:
        elig = E["not_active_key"]; ev = [spec["evidence"]["not_active"].format(incident=p["incident"], start=p["start"])]
    elif p["incident"] <= p["start"] + datetime.timedelta(days=2):
        elig = E["review_key"]; ev = [spec["evidence"]["review"].format(incident=p["incident"], start=p["start"])]
    elif any(k in state for k in E["excluded_peril_words"]) and p.get("tier") in E["excluded_tiers"]:
        elig = E["excluded_key"]; ev = [spec["evidence"]["excluded"].format(tier=p.get("tier"))]
    else:
        elig = E["ok_key"]; ev = [spec["evidence"]["elig_ok"]]
    answers[A["eligibility"]] = {"type": "choice", "choice": elig}
    evidence[A["eligibility"]] = ev

    ded = spec["deductibles"].get(p.get("cat", ""), None)
    if ded is None or "amount" not in p:
        band = "unparsed"; ev = [spec["evidence"]["no_amount"]]
    else:
        pay = 0 if (flag or elig != E["ok_key"]) else max(0, p["amount"] - ded)
        band = band_key(pay, Q["band_zero_key"], Q["band_keys"])
        ev = [spec["evidence"]["band_math"].format(amount=p["amount"], ded=ded, pay=pay)]
    answers[A["money_band"]] = {"type": "choice", "choice": band}
    evidence[A["money_band"]] = ev

    tp = spec["third_party"]
    yes = any(k in state for k in tp["always_words"]) or \
          (any(k in state for k in tp["with_docs_words"]) and p.get("docs_ok"))
    answers[A["third_party"]] = {"type": "noul", "noul": 1.0 if yes else 0.0}
    evidence[A["third_party"]] = [tp["evidence_yes"] if yes else tp["evidence_no"]]

    comps = (0 if p.get("docs_ok") else 1) + (1 if p.get("amount", 0) >= HIGH_VALUE else 0) + \
            (0 if elig == E["ok_key"] else 1)
    touches = 3 if flag else min(3, comps)
    answers[A["touches"]] = {"type": "score", "score": touches}
    evidence[A["touches"]] = [f"complications={comps}" + (" + flag" if flag else "")]

    return {"engine": f"rules-{spec['name']}", "ms": 0.1, "answers": answers, "evidence": evidence}


# ---------------- policy changes (Domain Builder: "change the rulebook, re-teach") ----------------
# A policy change is a spec edit. decide() under the edited spec recomputes the rule answer for
# any template state, so relabeled training rows and the exam's "new rule" answers stay
# rule-verifiable. Three kinds, each one plain-English sentence with editable values:
#   reassign  {cat, unit}     unflagged cases of one category go to another desk   (routing)
#   vip       {tier, level}   a tier's cases are at least this urgent              (urgency)
#   risk      {markers}       warning signs needed before a review flag (was 2)    (routing,
#                             risk flag, money band, touches)
URGENCY_NAMES = ["routine", "priority", "urgent", "critical"]
POLICY_KINDS = ("reassign", "vip", "risk")
MEMO_PREFIX = "POLICY UPDATE (effective today; overrides any rule above): "


def _human(key):
    return str(key).replace("_", " ")


def policy_choices(spec):
    """Allowed values per policy kind and parameter (the rulebook editor's dropdowns)."""
    A = spec["questions"]["archetypes"]
    return {"reassign": {"cat": list(spec["categories"]),
                         "unit": list(spec["questions"]["defs"][A["routing"]]["criteria"])},
            "vip": {"tier": list(spec.get("tiers", TIERS)), "level": [1, 2, 3]},
            "risk": {"markers": [1, 2, 3]}}


def normalize_policy(spec, pol):
    """{kind, params} with every value checked against policy_choices; ValueError otherwise."""
    if not isinstance(pol, dict) or pol.get("kind") not in POLICY_KINDS:
        raise ValueError(f"policy kind must be one of {', '.join(POLICY_KINDS)}")
    allowed = policy_choices(spec)[pol["kind"]]
    params = pol.get("params") if isinstance(pol.get("params"), dict) else {}
    out = {}
    for name, values in allowed.items():
        v = params.get(name)
        if v not in values:
            raise ValueError(f"{pol['kind']}.{name} must be one of {values}")
        out[name] = v
    return {"kind": pol["kind"], "params": out}


def policy_sentence(spec, pol):
    """The policy as one plain-English rule (also appended to the affected instructions)."""
    k, p = pol["kind"], pol["params"]
    nouns = spec.get("noun_plural", "cases")
    if k == "reassign":
        old = spec["categories"][p["cat"]]["unit"]
        return (f"{_human(p['cat']).capitalize()} {nouns} that are not flagged for review go to "
                f"{_human(p['unit'])} (previously {_human(old)}).")
    if k == "vip":
        return f"{p['tier']}-tier {nouns} are always at least {URGENCY_NAMES[p['level']]}."
    n = p["markers"]
    return (f"Flag for review when at least {n} warning sign{'s' if n > 1 else ''} "
            f"appear{'s' if n == 1 else ''} (previously 2).")


def policy_is_noop(spec, pol):
    """True when the edited rule is today's rule (nothing to teach)."""
    k, p = pol["kind"], pol["params"]
    if k == "reassign":
        return spec["categories"][p["cat"]]["unit"] == p["unit"]
    if k == "risk":
        return p["markers"] == spec["signals"].get("flag_markers", 2)
    return False


def apply_policy(spec, pol):
    """A deep copy of `spec` under the policy, with the rule appended to the affected questions."""
    import copy
    s = copy.deepcopy(spec)
    k, p = pol["kind"], pol["params"]
    A = s["questions"]["archetypes"]
    if k == "reassign":
        s["categories"][p["cat"]]["unit"] = p["unit"]
        qids = [A["routing"]]
    elif k == "vip":
        s["urgency"]["tier_floor"] = {p["tier"]: p["level"]}
        qids = [A["urgency"]]
    else:
        s["signals"]["flag_markers"] = p["markers"]
        qids = [A["routing"], A["risk_flag"]]
    memo = MEMO_PREFIX + policy_sentence(spec, pol)
    for q in qids:
        s["questions"]["defs"][q]["instructions"] += " " + memo
    return s


def rule_gold(spec, state):
    """decide() answers as gold values (bool / int / option key), or None if any is unparsed."""
    gold = {}
    for qid, a in decide(spec, state)["answers"].items():
        if a["type"] == "noul":
            gold[qid] = a["noul"] > 0.5
        elif a["type"] == "score":
            gold[qid] = int(a["score"])
        elif a["choice"] == "unparsed":
            return None
        else:
            gold[qid] = a["choice"]
    return gold


def changed_decisions(old_gold, new_gold):
    """Question ids whose rule answer differs between two gold dicts."""
    return [q for q in old_gold if new_gold.get(q) != old_gold[q]]


def policy_training_rows(spec, train_rows, pol, n_changed=300, n_same=300, seed=11):
    """Re-teach set for a policy: corpus rows relabeled under the new rule.

    `n_changed` rows whose answers the policy changes (all of them when fewer exist) plus
    `n_same` it leaves alone — the second half keeps the rest of the rulebook in place. Rows
    carry the policy's question defs, so the taught model reads the updated rule text."""
    import random as _random
    new_spec = apply_policy(spec, pol)
    defs = new_spec["questions"]["defs"]
    changed, same = [], []
    for t in train_rows:
        new = rule_gold(new_spec, t["state"])
        if new is None:
            continue
        row = {"state": t["state"], "questions": defs, "expected": new}
        (changed if changed_decisions(t["expected"], new) else same).append(row)
    rng = _random.Random(seed)
    rows = rng.sample(changed, min(n_changed, len(changed))) + rng.sample(same, min(n_same, len(same)))
    rng.shuffle(rows)
    return rows, len(changed), len(same)


def policy_exam(spec, holdout_rows, pol, n_changed=12, n_same=12):
    """Unseen exam for a policy: the first `n_changed` holdout rows the policy changes and the
    first `n_same` it does not, in file order (deterministic, disjoint from training rows)."""
    new_spec = apply_policy(spec, pol)
    changed, same = [], []
    for r in holdout_rows:
        new = rule_gold(new_spec, r["state"])
        if new is None:
            continue
        diff = changed_decisions(r["gold"], new)
        bucket = changed if diff else same
        if len(bucket) < (n_changed if diff else n_same):
            bucket.append({"id": r["id"], "state": r["state"], "old_gold": r["gold"],
                           "new_gold": new, "changed": diff})
        if len(changed) >= n_changed and len(same) >= n_same:
            break
    return changed + same
