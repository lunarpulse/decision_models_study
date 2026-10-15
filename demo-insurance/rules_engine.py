"""Engine D: the incumbent rules engine, implemented honestly.

The rules are EXACTLY the ones stated in the demo question instructions (the insurer's written
policy), applied by keyword/regex/date parsing to raw claim text — the way a real first-gen
automation stack would implement them. Every answer carries its evidence (which rule fired, or
what failed to parse), which the console shows as the audit trail. Non-English claims cannot be
parsed by keyword rules and are returned as unparsed: that gap is the demo's point.

Importable both by the live service (/rules) and by build_portfolio.py (offline scoring).
"""
import re, datetime

TODAY = datetime.date(2026, 10, 8)
DED = {"MOTOR": 500, "PROPERTY": 1000, "HEALTH": 250, "TRAVEL": 100}

_CAT_WORDS = {
    "motor_unit": ["hail", "car", "parking garage", "windshield", "road debris", "standing water", "rear-ended", "side-swiped", "traffic light", "bumper", "trunk"],
    "property_unit": ["kitchen", "cabinets", "burst pipe", "basement", "shingles", "roof", "break-in", "back door", "electronics", "tree fell", "garage during high winds"],
    "health_benefits": ["emergency room", "fractured wrist", "specialist consultation", "back pain", "prescription", "medication", "physiotherapy", "knee surgery", "urgent care", "allergic reaction", "kidney stone"],
    "travel_unit": ["flight cancellation", "hotel night", "checked baggage", "trip interrupted", "tour operator", "excursion", "cruise", "delayed connection", "return flight"],
}
_HOSP_WORDS = ["emergency room", "urgent care", "hospitalization"]
_INJURY_WORDS = ["fractured", "back pain", "knee surgery", "physiotherapy", "allergic reaction", "injury", "kidney stone"]
_HOME_LOSS_WORDS = ["flooded the basement"]


def _parse(state):
    m = {}
    pol = re.search(r"(?:Policy|policy|póliza|ポリシー|पॉलिसी|정책)\s+([A-Z]+)-\d+", state)
    if pol:
        m["pol_type"] = pol.group(1)
    ps = re.search(r"(?:started|began|comenzó|開始|आरंभ|시작되었습니다)\s*:?\.?\s*(\d{4}-\d{2}-\d{2})", state)
    if ps:
        m["policy_start"] = datetime.date.fromisoformat(ps.group(1))
    inc = re.search(r"(?:The incident:.*?|出来事：.*?|घटना:.*?|사고:.*?)(\d{4}-\d{2}-\d{2})", state)
    if inc:
        m["incident"] = datetime.date.fromisoformat(inc.group(1))
    amt = re.search(r"(?:USD|usd|米ドル|अमेरिकी डॉलर|달러)\s*([\d,]+)", state) or \
          re.search(r"([\d,]+)\s*(?:USD|usd|米ドル|अमेरिकी डॉलर|달러)", state)
    if amt:
        m["amount"] = int(amt.group(1).replace(",", ""))
    tier = re.search(r"(?:plan tier is|tier)\s+(Basic|Standard|Plus|Premium)", state)
    if tier:
        m["tier"] = tier.group(1)
    m["docs_ok"] = "No supporting documents" not in state
    return m


_QIDS = ["fraud_review", "routing", "urgency", "coverage_eligibility",
         "net_payable_band", "subrogation", "expected_touches"]

_UNPARSED_EV = ["claim not parsed: incident date or amount not found "
                "(non-English or unfamiliar wording) — no rule answers attempted"]


def decide(state, questions=None):
    """Return {answers: {qid: {...}}, evidence: {qid: [strings]}, ms, engine: 'rules-v1'}."""
    p = _parse(state)
    if p.get("incident") is None or p.get("amount") is None:
        # Keyword rules are English-only. If the incident date or amount could not be
        # parsed, EVERY question comes back "unparsed" (the same representation the
        # routing/coverage branches already use) instead of confidently wrong defaults
        # (band=zero_nothing_payable, touches, fraud=0, ...).
        answers = {qid: {"type": "choice", "choice": "unparsed"} for qid in _QIDS}
        evidence = {qid: list(_UNPARSED_EV) for qid in _QIDS}
        return {"engine": "rules-v1", "ms": 0.1, "answers": answers, "evidence": evidence}
    answers, evidence = {}, {}

    fired = []
    if not p.get("docs_ok"):
        fired.append("no supporting documents attached")
    if p.get("policy_start") and p["policy_start"] >= TODAY - datetime.timedelta(days=30):
        fired.append(f"policy started {p['policy_start']} (within 30 days of filing)")
    if p.get("amount", 0) >= 18500:
        fired.append(f"claimed amount USD {p['amount']:,} >= 18,500")
    fraud = len(fired) >= 2
    answers["fraud_review"] = {"type": "noul", "noul": 1.0 if fraud else 0.0}
    evidence["fraud_review"] = fired or ["no fraud markers fired"]

    if p.get("pol_type") is None:
        answers["routing"] = {"type": "choice", "choice": "unparsed"}
        evidence["routing"] = ["no policy prefix (MOTOR/PROPERTY/HEALTH/TRAVEL) found in text"]
    elif fraud:
        answers["routing"] = {"type": "choice", "choice": "special_investigations"}
        evidence["routing"] = ["2+ fraud markers fired -> special investigations"]
    else:
        scores = {u: sum(w in state for w in ws) for u, ws in _CAT_WORDS.items()}
        unit = max(scores, key=scores.get) if max(scores.values()) > 0 else "unparsed"
        answers["routing"] = {"type": "choice", "choice": unit}
        if unit == "unparsed":
            evidence["routing"] = ["no category keywords matched"]
        else:
            evidence["routing"] = [f"keyword match: {unit} ({scores[unit]} hits)"]

    if any(h in state for h in _HOSP_WORDS):
        urg = 3
    elif any(w in state for w in _INJURY_WORDS) or any(w in state for w in _HOME_LOSS_WORDS):
        urg = 2
    elif p.get("amount", 0) >= 8800 or any(w in state for w in _CAT_WORDS["travel_unit"]):
        urg = 1
    else:
        urg = 0
    answers["urgency"] = {"type": "score", "score": urg}
    evidence["urgency"] = [f"rule level {urg}"]

    if not p.get("incident") or not p.get("policy_start"):
        elig = "unparsed"
        ev = ["incident or policy start date not parsed from text"]
    elif p["incident"] < p["policy_start"]:
        elig = "not_covered_policy_not_active"
        ev = [f"incident {p['incident']} precedes policy start {p['policy_start']}"]
    elif p["incident"] <= p["policy_start"] + datetime.timedelta(days=2):
        elig = "review_required"
        ev = [f"incident {p['incident']} within 2 days of policy start {p['policy_start']}"]
    elif "flooded engine" in state and p.get("tier") in ("Basic", "Standard"):
        elig = "not_covered_peril_excluded"
        ev = [f"flood damage excluded on {p.get('tier')} plan"]
    else:
        elig = "covered"
        ev = ["policy active for the incident; peril included in plan"]
    answers["coverage_eligibility"] = {"type": "choice", "choice": elig}
    evidence["coverage_eligibility"] = ev

    ded = DED.get(p.get("pol_type", ""), None)
    if ded is None or p.get("amount") is None:
        band, ev = "unparsed", ["policy type or amount not parsed"]
    else:
        pay = 0 if (fraud or elig != "covered") else max(0, p["amount"] - ded)
        band = ("zero_nothing_payable" if pay == 0 else "up_to_1000" if pay <= 1000 else
                "1000_to_5000" if pay <= 5000 else "5000_to_15000" if pay <= 15000 else "over_15000")
        ev = [f"USD {p['amount']:,} - deductible USD {ded:,} = USD {pay:,}"]
    answers["net_payable_band"] = {"type": "choice", "choice": band}
    evidence["net_payable_band"] = ev

    subro = "rear-ended at a traffic light" in state or \
            ("side-swiped in a parking garage" in state and p.get("docs_ok"))
    answers["subrogation"] = {"type": "noul", "noul": 1.0 if subro else 0.0}
    evidence["subrogation"] = (["identified liable third party (rear-end / garage collision with report)"]
                               if subro else ["no identified third party"])

    comps = (0 if p.get("docs_ok") else 1) + (1 if p.get("amount", 0) >= 8800 else 0) + \
            (0 if elig == "covered" else 1)
    touches = 3 if fraud else min(3, comps)
    answers["expected_touches"] = {"type": "score", "score": touches}
    evidence["expected_touches"] = [f"complications={comps}" + (" + fraud flag" if fraud else "")]

    return {"engine": "rules-v1", "ms": 0.1, "answers": answers, "evidence": evidence}
