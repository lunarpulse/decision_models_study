"""Insurance-claims demo corpus generator (rule-verifiable gold, seeded).

Emits: train.jsonl (12k), validation.jsonl (2k), holdout_eval.jsonl (500), demo_presets.json (curated).
Row schema matches laya-train expectations: {state, questions, expected} for train; gold kept as
`gold` for eval rows (converted per consumer).
"""
import json, random, pathlib, datetime

OUT = pathlib.Path(__file__).resolve().parent / "data"
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(20261008)

CATEGORIES = {
    "motor": dict(
        unit="motor_unit",
        things=["rear-ended at a traffic light", "hail damage to the roof and hood",
                "side-swiped in a parking garage", "windshield cracked by road debris",
                "flooded engine after driving through standing water"],
        docs=["repair estimate", "photos of the damage", "police report reference"],
    ),
    "property": dict(
        unit="property_unit",
        things=["kitchen fire damaged cabinets and countertops", "burst pipe flooded the basement",
                "storm tore shingles off the roof", "break-in damaged the back door and stole electronics",
                "tree fell on the garage during high winds"],
        docs=["contractor quote", "photos of the damage", "incident report reference"],
    ),
    "health": dict(
        unit="health_benefits",
        things=["emergency room visit for a fractured wrist", "specialist consultation for back pain",
                "prescription coverage for a new medication", "physiotherapy sessions after knee surgery",
                "urgent care visit for a severe allergic reaction"],
        docs=["itemized hospital invoice", "referral letter", "prescription copy"],
    ),
    "travel": dict(
        unit="travel_unit",
        things=["flight cancellation forced an unplanned hotel night", "lost checked baggage on a return flight",
                "trip interrupted by a family medical emergency", "tour operator cancelled the booked excursion",
                "delayed connection caused missed cruise departure"],
        docs=["airline confirmation", "hotel receipt", "booking itinerary"],
    ),
}

AMOUNTS = [240, 480, 850, 1200, 1650, 2100, 2800, 3400, 4200, 5100, 6300, 7400, 8800, 9600, 11200, 13400, 15800, 18500, 22000, 26500]
FIRST = ["J.", "M.", "A.", "R.", "S.", "K.", "L.", "D.", "P.", "T."]
NAMES = ["Alvarez", "Bennett", "Cho", "Dubois", "Eriksen", "Ferreira", "Gupta", "Haddad", "Ibrahim", "Johnson",
         "Kim", "Larsen", "Martin", "Nakamura", "Okafor", "Park", "Quinn", "Rossi", "Silva", "Tanaka",
         "Ueda", "Vargas", "Wong", "Yoon", "Zhang"]
CHANNELS = ["the mobile app", "the web portal", "the claims hotline", "an email to the claims desk"]

QUESTIONS = {
    "routing": {
        "type": "choice",
        "instructions": ("You are routing one insurance claim to the unit that should handle it. "
                         "Choose exactly one unit. Rule: if the claim shows at least two fraud warning "
                         "signs (no verifiable documents, filed very soon after policy start, or an "
                         "unusually large amount), route to special investigations regardless of claim type."),
        "criteria": {
            "motor_unit": "Vehicle accidents, hail, flood or parking damage to a car.",
            "property_unit": "Home damage: fire, water, storm, theft or structural damage.",
            "health_benefits": "Medical, dental, prescription or therapy cost reimbursement.",
            "travel_unit": "Trip cancellation, delay, lost baggage or interrupted travel.",
            "special_investigations": "Claims with repeated fraud warning signs needing review before payout.",
        },
    },
    "fraud_review": {
        "type": "noul",
        "instructions": ("Should this claim be flagged for special investigation before payout? "
                         "Answer yes only when at least two fraud warning signs appear: missing "
                         "verifiable documents, claim filed within 30 days of policy start, or an "
                         "unusually large claimed amount."),
    },
    "urgency": {
        "type": "score",
        "instructions": ("How urgently should this claim be worked? critical: medical emergency or "
                         "hospitalization involved. urgent: injury reported or the home is "
                         "uninhabitable. priority: high-value claim or time-sensitive travel "
                         "disruption. routine: everything else."),
        "criteria": ["routine", "priority", "urgent", "critical"],
    },
    "coverage_eligibility": {
        "type": "choice",
        "instructions": ("Is this loss covered by the quoted policy? Rules: the incident must fall "
                         "on or after the policy start date (earlier incidents are not covered). "
                         "An incident within 2 days after policy start needs manual review before "
                         "coverage is confirmed. Vehicle flood damage is covered only on Plus or "
                         "Premium plans. Otherwise the loss is covered."),
        "criteria": {
            "covered": "Policy active for the incident and the peril is included in the plan.",
            "not_covered_policy_not_active": "The incident happened before the policy start date.",
            "not_covered_peril_excluded": "The plan tier excludes this peril (flood damage on Basic or Standard vehicle plans).",
            "review_required": "Incident within 2 days of policy start; a coverage check must precede any payment.",
        },
    },
    "net_payable_band": {
        "type": "choice",
        "instructions": ("After the plan deductible is applied, which band does the net payable "
                         "amount fall into? Deductibles: motor USD 500, property USD 1,000, "
                         "health USD 250, travel USD 100. If the claim is not covered or is held "
                         "for special investigation, nothing is payable yet (USD 0)."),
        "criteria": {
            "zero_nothing_payable": "Not covered, under review, or payout held for investigation.",
            "up_to_1000": "Net payable USD 1 - 1,000 after the deductible.",
            "1000_to_5000": "Net payable USD 1,001 - 5,000 after the deductible.",
            "5000_to_15000": "Net payable USD 5,001 - 15,000 after the deductible.",
            "over_15000": "Net payable over USD 15,000 after the deductible.",
        },
    },
    "subrogation": {
        "type": "noul",
        "instructions": ("Should the insurer pursue a third party to recover the payout "
                         "(subrogation)? Answer yes only when a liable third party is identified "
                         "in the claim: another driver rear-ended the customer, or a parking-garage "
                         "collision with a police report naming the other party."),
    },
    "expected_touches": {
        "type": "score",
        "instructions": ("How many adjuster touches will this claim need? 0-1: complete, documented, "
                         "low-value claim (straight-through candidate). 2: one complication - missing "
                         "documents, high value (USD 8,800+), or a coverage check. 3: two complications. "
                         "4+: fraud-flagged or three complications."),
        "criteria": ["0-1 touches (straight-through candidate)", "2 touches", "3 touches", "4+ touches / investigator assigned"],
    },
}

JOURNEY_STAGES = [
    {"stage": "1 · Intake & triage", "questions": ["routing", "urgency"]},
    {"stage": "2 · Coverage & payment", "questions": ["coverage_eligibility", "net_payable_band"]},
    {"stage": "3 · Investigation", "questions": ["fraud_review", "subrogation"]},
    {"stage": "4 · Operations", "questions": ["expected_touches"]},
]


def make_row(i, force=None):
    cat = force["cat"] if force else rng.choice(list(CATEGORIES))
    spec = CATEGORIES[cat]
    thing = rng.choice(spec["things"])
    amount = rng.choice(AMOUNTS)
    policy_days = rng.choice([3, 9, 17, 26, 45, 80, 140, 260, 400, 700])
    docs_ok = rng.random() < 0.72
    tier = rng.choice(['Basic', 'Standard', 'Plus', 'Premium'])
    injury = "injury" in thing or "fractured" in thing or "allergic" in thing or "back pain" in thing or "knee surgery" in thing
    hospital = ("emergency room" in thing) or ("urgent care" in thing)
    uninhabitable = "flooded the basement" in thing

    markers = 0
    if not docs_ok: markers += 1
    if policy_days <= 30: markers += 1
    if amount >= 18500: markers += 1
    fraud = markers >= 2

    name = rng.choice(FIRST) + " " + rng.choice(NAMES)
    today = datetime.date(2026, 10, 8)
    filed = today - datetime.timedelta(days=rng.choice([0, 1, 2, 4, 7]))
    incident = filed - datetime.timedelta(days=rng.choice([0, 1, 2, 5, 9]))
    policy_start = today - datetime.timedelta(days=policy_days)

    gold = {}
    gold["routing"] = "special_investigations" if fraud else spec["unit"]
    gold["fraud_review"] = fraud
    if hospital: gold["urgency"] = 3
    elif injury or uninhabitable: gold["urgency"] = 2
    elif amount >= 8800 or cat == "travel": gold["urgency"] = 1
    else: gold["urgency"] = 0

    # ---- v2 journey gold (all rules stated in the question instructions) ----
    if incident < policy_start:
        gold["coverage_eligibility"] = "not_covered_policy_not_active"
    elif incident <= policy_start + datetime.timedelta(days=2):
        gold["coverage_eligibility"] = "review_required"
    elif thing.startswith("flooded engine") and tier in ("Basic", "Standard"):
        gold["coverage_eligibility"] = "not_covered_peril_excluded"
    else:
        gold["coverage_eligibility"] = "covered"

    deductible = {"motor": 500, "property": 1000, "health": 250, "travel": 100}[cat]
    payable = 0 if (fraud or gold["coverage_eligibility"] != "covered") else max(0, amount - deductible)
    gold["net_payable_band"] = ("zero_nothing_payable" if payable == 0 else
                                "up_to_1000" if payable <= 1000 else
                                "1000_to_5000" if payable <= 5000 else
                                "5000_to_15000" if payable <= 15000 else
                                "over_15000")

    gold["subrogation"] = (thing == "rear-ended at a traffic light" or
                           (thing == "side-swiped in a parking garage" and docs_ok))

    complications = (0 if docs_ok else 1) + (1 if amount >= 8800 else 0) + \
                    (0 if gold["coverage_eligibility"] == "covered" else 1)
    gold["expected_touches"] = 3 if fraud else min(3, complications)


    doc_phrase = ("The customer attached the " + " and ".join(spec["docs"]) + "."
                  if docs_ok else
                  "No supporting documents were attached; the customer says they were lost in a move.")
    amount_phrase = f"USD {amount:,}"
    if amount >= 18500 and rng.random() < 0.5:
        amount_phrase = f"USD {amount:,} (the customer asks for the policy limit)"

    state = (
        f"Insurance claim CLM-{90000+i} filed by {name} on {filed.isoformat()} through {rng.choice(CHANNELS)}. "
        f"Policy {cat.upper()}-{5000+i} started {policy_start.isoformat()}. "
        f"The incident: {thing}, on {incident.isoformat()}. "
        f"Claimed amount: {amount_phrase}. {doc_phrase} "
        f"The customer's plan tier is {tier}."
    )
    return {"id": f"ins-{i:06d}", "state": state, "questions": QUESTIONS, "gold": gold,
            "meta": {"cat": cat, "amount": amount, "policy_days": policy_days,
                     "docs_ok": docs_ok, "fraud": fraud, "hospital": hospital,
                     "injury": injury, "uninhabitable": uninhabitable,
                     "tier": tier, "deductible": deductible, "payable": payable,
                     "incident_iso": incident.isoformat(), "filed_iso": filed.isoformat(),
                     "policy_start_iso": policy_start.isoformat(),
                     "complications": complications}}


def to_train(r):
    return {"state": r["state"], "questions": r["questions"], "expected": r["gold"]}


def preset_label(r):
    """Preset label describing the claim that was ACTUALLY generated (only cat + fraud are
    forced; docs/policy age/amount are whatever the row drew). Reads meta/state only —
    no rng calls, so train/validation/holdout bytes are unaffected."""
    m = r["meta"]
    thing = r["state"].split("The incident: ", 1)[1].split(", on ")[0]  # English rows only
    if not m["fraud"]:
        return f"{m['cat']} · {thing} · " + ("docs attached" if m["docs_ok"] else "no docs")
    flags = []
    if not m["docs_ok"]: flags.append("no docs")
    if m["policy_days"] <= 30: flags.append("fresh policy")
    if "asks for the policy limit" in r["state"]: flags.append("limit ask")
    if m["amount"] >= 18500: flags.append("huge amount")
    return "FRAUD: " + f"{m['cat']} · {thing} · " + " + ".join(flags)


rows = {}
seen = set()
i = 0
# 15,480 target = 14,500 consumed (12k/2k/500) + 980-row surplus margin so preset
# forces can be drawn from the same seeded pool. Changing this number changes all SHAs.
while len(rows) < 15480:
    r = make_row(i)
    key = r["state"]
    if key not in seen:
        seen.add(key)
        rows[r["id"]] = r
    i += 1
all_rows = list(rows.values())
rng.shuffle(all_rows)

train, validation, holdout = all_rows[:12000], all_rows[12000:14000], all_rows[14000:14500]

with open(OUT / "train.jsonl", "w") as f:
    for r in train: f.write(json.dumps(to_train(r)) + "\n")
with open(OUT / "validation.jsonl", "w") as f:
    for r in validation: f.write(json.dumps(to_train(r)) + "\n")
with open(OUT / "holdout_eval.jsonl", "w") as f:
    for r in holdout: f.write(json.dumps(r) + "\n")

# ---- curated presets (deterministic forces, hand-checked rules) ----
forces = [
    {"cat": "motor", "desc": "plain motor claim, docs attached"}, {"cat": "motor", "desc": "motor hail damage"},
    {"cat": "property", "desc": "kitchen fire"}, {"cat": "property", "desc": "burst pipe"},
    {"cat": "health", "desc": "ER fracture"}, {"cat": "health", "desc": "prescription"},
    {"cat": "travel", "desc": "flight cancellation"}, {"cat": "travel", "desc": "lost baggage"},
    {"cat": "motor", "desc": "FRAUD: no docs + fresh policy"}, {"cat": "property", "desc": "FRAUD: no docs + huge amount"},
    {"cat": "health", "desc": "FRAUD: fresh policy + limit ask"}, {"cat": "travel", "desc": "FRAUD: no docs + limit ask"},
    {"cat": "property", "desc": "break-in theft"}, {"cat": "motor", "desc": "flooded engine"},
    {"cat": "health", "desc": "physiotherapy"}, {"cat": "travel", "desc": "missed cruise"},
]
presets = []
for k, force in enumerate(forces):
    for attempt in range(4000):
        r = make_row(990000 + k * 100 + attempt, force=force)
        m = r["meta"]
        want_fraud = "FRAUD" in force["desc"]
        want_hosp = "ER" in force["desc"]
        want_injury = force["desc"] in ("ER fracture",)
        ok = (m["fraud"] == want_fraud)
        if "ER" in force["desc"]: ok = ok and r["gold"]["urgency"] == 3
        if ok:
            presets.append({"label": preset_label(r), "id": r["id"], "state": r["state"],
                            "gold": r["gold"], "meta": m})
            break

MULTILINGUAL = [
    {"label": "🇰🇷 Korean motor claim", "lang": "ko",
     "state": "보험 청구 CLM-771001. 정책 MOTOR-7710은 2026년 4월 1일에 시작되었습니다. 사고: 신호등에서 추돌 사고가 발생했고, 후미 범퍼와 트렁크가 파손되었습니다. 청구 금액: USD 2,400. 고객은 수리 견적서와 사진을 첨부했습니다.",
     "gold": {"routing": "motor_unit", "fraud_review": False, "urgency": 0,
              "coverage_eligibility": "covered", "net_payable_band": "1000_to_5000",
              "subrogation": True, "expected_touches": 0}},
    {"label": "🇯🇵 Japanese property claim", "lang": "ja",
     "state": "保険請求 CLM-771002。ポリシー PROPERTY-7720 は 2026年3月15日に開始。出来事：台風で屋根の屋根板が剥がされました。請求額：6,300米ドル。お客様は業者の見積書と写真を添付しています。",
     "gold": {"routing": "property_unit", "fraud_review": False, "urgency": 0,
              "coverage_eligibility": "covered", "net_payable_band": "5000_to_15000",
              "subrogation": False, "expected_touches": 0}},
    {"label": "🇮🇳 Hindi health claim", "lang": "hi",
     "state": "बीमा दावा CLM-771003। पॉलिसी HEALTH-7730 का आरंभ 2026-09-20 को हुआ। घटना: गुर्दे की पथरी के इलाज के लिए आपातकालीन कक्ष में भर्ती। दावा राशि: 17,500 अमेरिकी डॉलर। अस्पताल का विस्तृत बिल और पर्चा प्रति संलग्न है।",
     "gold": {"routing": "health_benefits", "fraud_review": False, "urgency": 3,
              "coverage_eligibility": "covered", "net_payable_band": "over_15000",
              "subrogation": False, "expected_touches": 1}},
    {"label": "🇪🇸 Spanish travel claim", "lang": "es",
     "state": "Reclamación de seguro CLM-771004. La póliza TRAVEL-7740 comenzó el 2026-01-10. Incidente: el vuelo de regreso fue cancelado y hubo que pagar una noche de hotel no planificada. Importe: 480 USD. El cliente adjuntó la confirmación de la aerolínea y el recibo del hotel.",
     "gold": {"routing": "travel_unit", "fraud_review": False, "urgency": 1,
              "coverage_eligibility": "covered", "net_payable_band": "up_to_1000",
              "subrogation": False, "expected_touches": 0}},
]
presets.extend(MULTILINGUAL)

with open(OUT / "demo_presets.json", "w") as f:
    json.dump({"questions": QUESTIONS, "stages": JOURNEY_STAGES, "presets": presets}, f, indent=1, ensure_ascii=False)

import collections
print("train", len(train), "val", len(validation), "holdout", len(holdout), "presets", len(presets))
print("train fraud rate", sum(r["meta"]["fraud"] for r in train) / len(train))
print("routing dist", dict(collections.Counter(r["gold"]["routing"] for r in train)))
print("urgency dist", dict(collections.Counter(r["gold"]["urgency"] for r in train)))
print("eligibility dist", dict(collections.Counter(r["gold"]["coverage_eligibility"] for r in train)))
print("payable band dist", dict(collections.Counter(r["gold"]["net_payable_band"] for r in train)))
print("subrogation rate", sum(r["gold"]["subrogation"] for r in train) / len(train))
print("touches dist", dict(collections.Counter(r["gold"]["expected_touches"] for r in train)))
print("presets labels:", [p["label"] for p in presets])
