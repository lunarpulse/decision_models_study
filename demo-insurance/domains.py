"""Domain specs for the Domain Builder (demo v3). Insurance lives in gen_corpus.py (frozen).

Each spec is declarative: vocab, params, question wording (rules stated verbatim in the
instructions), state template + parser regexes (renderer/regex pairs), evidence strings, and
hand-written paraphrase probes. domain_factory.py consumes these.
"""
import datetime

# ---------------------------------------------------------------- support_tickets
SUPPORT_TICKETS = {
    "name": "support_tickets",
    "id_prefix": "TCK",
    "rng_seed": 20261015,
    "today": datetime.date(2026, 10, 8),
    "counts": {"train": 2000, "val": 2000, "holdout": 500, "surplus": 480},

    "state_template": ("Support ticket {prefix}-{n} opened by {name} on {filed} via {channel}. "
                       "Account {cat}-{ref} opened {start}. The issue: {thing}, first reported {incident}. "
                       "Requested refund: {amount_phrase}. {doc_phrase} The customer's plan is {tier}."),

    "channels": ["the support portal", "email to the help desk", "the in-app chat", "the priority phone line"],

    "categories": {
        "billing": {
            "unit": "billing_desk",
            "things": ["duplicate charge on the monthly invoice",
                       "plan upgrade billed at the wrong rate",
                       "proration error after a mid-cycle downgrade",
                       "charge for a cancelled add-on",
                       "double charge routed through the payment gateway",
                       "VAT applied twice on the annual renewal"],
            "docs": ["invoice copy", "payment confirmation", "plan statement"],
        },
        "technical": {
            "unit": "technical_desk",
            "things": ["dashboard fails to load beyond a blank page",
                       "API returns 500 errors on every request",
                       "webhook deliveries stopped arriving",
                       "export job stuck in queue for hours",
                       "data loss after the sync rollback",
                       "outage affecting the whole workspace",
                       "third-party integration failure in the shipping partner's plugin"],
            "docs": ["error log excerpt", "screenshot of the failure", "request IDs"],
        },
        "account": {
            "unit": "account_security",
            "things": ["account locked after repeated 2FA failures",
                       "password reset email never arrives",
                       "unrecognized device in the login history",
                       "email change requested without the verification code",
                       "login loop after the SSO migration",
                       "MFA device lost during a phone upgrade"],
            "docs": ["identity confirmation", "recent activity export", "support PIN"],
        },
        "feature": {
            "unit": "product_team",
            "things": ["reporting add-on purchased but not activated",
                       "priority support tier bought and still throttled",
                       "onboarding credit promised by sales not applied",
                       "marketplace template bought but not downloadable",
                       "sandbox upgrade charged but still on the free limits",
                       "additional seat pack paid for and not provisioned"],
            "docs": ["purchase confirmation", "sales email excerpt", "addon invoice"],
        },
    },

    "signals": {
        "flag_unit": "trust_and_safety",
        "fresh_days": 30,
        "large_amount": 18500,
        "large_amount_suffix": "(the customer demands an immediate full refund plus compensation)",
        "today": datetime.date(2026, 10, 8),
    },

    "deductibles": {"billing": 25, "technical": 10, "account": 0, "feature": 50},

    "eligibility": {
        # "reporting add-on" is only sold on Plus/Premium; on Basic/Standard the purchase is voided
        "excluded_peril_words": ["reporting add-on"],
        "excluded_tiers": ["Basic", "Standard"],
        "ok_key": "eligible",
        "not_active_key": "outside_window_account_not_active",
        "review_key": "review_required_fresh_account",
        "excluded_key": "not_eligible_plan_exclusion",
    },

    "third_party": {
        "always_words": ["double charge routed through the payment gateway"],
        "with_docs_words": ["third-party integration failure in the shipping partner's plugin"],
        "evidence_yes": "identified vendor at fault (payment gateway / shipping partner with logs)",
        "evidence_no": "no vendor identified as the cause",
    },

    "urgency": {
        "critical_words": ["data loss", "outage affecting"],
        "urgent_words": ["locked", "login loop", "stuck in queue", "MFA device lost"],
        "priority_cats": ["account"],
    },

    "doc_ok_template": "The customer attached the {docs}.",

    "evidence": {
        "no_docs": "no supporting evidence attached",
        "fresh": "account opened {start} (within 30 days of the ticket)",
        "large": "refund demand USD {amount:,} >= 18,500",
        "no_markers": "no abuse markers fired",
        "no_ref": "no account reference (BILLING/TECHNICAL/ACCOUNT/FEATURE) found in text",
        "flag_route": "2+ abuse markers fired -> trust and safety",
        "keyword_route": "keyword match: {unit}",
        "no_dates": "account start or first-reported date not parsed from text",
        "not_active": "issue {incident} predates account opening {start}",
        "review": "issue {incident} within 2 days of account opening {start}",
        "excluded": "reporting add-on purchase voided on {tier} plan",
        "elig_ok": "issue inside account window; no plan exclusion",
        "no_amount": "queue or refund amount not parsed",
        "band_math": "USD {amount:,} - fee USD {ded:,} = USD {pay:,}",
    },
    "doc_missing_phrase": "No supporting evidence was attached; the customer says the files were lost.",
    "doc_missing_marker": "No supporting evidence",

    "parsers": {
        "ref": r"Account ([A-Z]+)-\d+",
        "start": r"Account [A-Z]+-\d+ opened (\d{4}-\d{2}-\d{2})",
        "incident": r"first reported (\d{4}-\d{2}-\d{2})",
        "amount": r"USD ([\d,]+)",
        "tier": r"plan is (Basic|Standard|Plus|Premium)",
    },

    "questions": {
        "archetypes": {"routing": "routing", "risk_flag": "abuse_review", "urgency": "urgency",
                       "eligibility": "refund_eligibility", "money_band": "refund_band",
                       "third_party": "vendor_recovery", "touches": "expected_touches"},
        "band_zero_key": "zero_nothing_payable",
        "band_keys": ["up_to_1000", "1000_to_5000", "5000_to_15000", "over_15000"],
        "defs": {
            "routing": {
                "type": "choice",
                "instructions": ("Route this support ticket to the team that should handle it. Choose "
                                 "exactly one team. Rule: if the ticket shows at least two abuse warning "
                                 "signs (no supporting evidence attached, an account younger than 30 days, "
                                 "or an unusually large refund demand over USD 18,500), route to trust and "
                                 "safety regardless of the issue type."),
                "criteria": {
                    "billing_desk": "Invoices, charges, proration, refunds of payments.",
                    "technical_desk": "Product failures: errors, outages, data loss, integrations.",
                    "account_security": "Logins, 2FA, device and identity issues.",
                    "product_team": "Purchased add-ons, seats and entitlements not delivered.",
                    "trust_and_safety": "Tickets with repeated abuse warning signs needing review.",
                },
            },
            "abuse_review": {
                "type": "noul",
                "instructions": ("Should this ticket be flagged for trust & safety review before any "
                                 "refund is issued? Answer yes only when at least two abuse warning signs "
                                 "appear: no supporting evidence, an account opened within 30 days of the "
                                 "ticket, or a refund demand over USD 18,500."),
            },
            "urgency": {
                "type": "score",
                "instructions": ("How urgently must this ticket be worked? critical: data loss or an "
                                 "outage affecting the whole workspace. urgent: the customer is locked "
                                 "out, stuck, or lost their MFA device. priority: account-security "
                                 "matters or a refund over USD 8,800. routine: everything else."),
                "criteria": ["routine", "priority", "urgent", "critical"],
            },
            "refund_eligibility": {
                "type": "choice",
                "instructions": ("Is this refund request eligible? Rules: the issue must fall inside the "
                                 "account's lifetime (an issue first reported before the account was "
                                 "opened is outside the window). An issue reported within 2 days of the "
                                 "account opening needs manual review. The reporting add-on is only sold "
                                 "on Plus or Premium plans — on Basic or Standard the purchase is voided "
                                 "and not refundable. Otherwise the request is eligible."),
                "criteria": {
                    "eligible": "Issue inside the account window and no plan exclusion applies.",
                    "outside_window_account_not_active": "The issue predates the account.",
                    "review_required_fresh_account": "Issue within 2 days of account opening; review first.",
                    "not_eligible_plan_exclusion": "Reporting add-on purchased on Basic/Standard (void sale).",
                },
            },
            "refund_band": {
                "type": "choice",
                "instructions": ("After the processing fee is applied, which band does the refund fall "
                                 "into? Fees: billing USD 25, technical USD 10, account USD 0, product "
                                 "team USD 50. If the request is not eligible or is held for trust & "
                                 "safety review, nothing is payable yet (USD 0)."),
                "criteria": {
                    "zero_nothing_payable": "Not eligible, needs review, or held for abuse review.",
                    "up_to_1000": "Refund USD 1 - 1,000 after the fee.",
                    "1000_to_5000": "Refund USD 1,001 - 5,000 after the fee.",
                    "5000_to_15000": "Refund USD 5,001 - 15,000 after the fee.",
                    "over_15000": "Refund over USD 15,000 after the fee.",
                },
            },
            "vendor_recovery": {
                "type": "noul",
                "instructions": ("Should the refund be recovered from a vendor (chargeback to the "
                                 "payment gateway or the shipping partner)? Answer yes only when a "
                                 "specific vendor is identified as the cause: a gateway double charge, "
                                 "or a shipping-partner integration failure with request logs attached."),
            },
            "expected_touches": {
                "type": "score",
                "instructions": ("How many agent touches will this ticket need? 0-1: complete, evidenced, "
                                 "low-value ticket (straight-through candidate). 2: one complication - "
                                 "missing evidence, a refund over USD 8,800, or an eligibility check. "
                                 "3: two complications. 4+: flagged for trust & safety or three "
                                 "complications."),
                "criteria": ["0-1 touches (straight-through candidate)", "2 touches", "3 touches",
                             "4+ touches / T&S investigator assigned"],
            },
        },
    },

    "stages": [
        {"stage": "1 · Intake & triage", "questions": ["routing", "urgency"]},
        {"stage": "2 · Refund & eligibility", "questions": ["refund_eligibility", "refund_band"]},
        {"stage": "3 · Investigation", "questions": ["abuse_review", "vendor_recovery"]},
        {"stage": "4 · Operations", "questions": ["expected_touches"]},
    ],

    "preset_forces": [
        {"cat": "billing", "desc": "plain billing refund, evidence attached", "want_flag": False},
        {"cat": "billing", "desc": "gateway double charge", "want_flag": False},
        {"cat": "technical", "desc": "API 500 errors", "want_flag": False},
        {"cat": "technical", "desc": "workspace outage", "want_flag": False, "want_urgency": 3},
        {"cat": "technical", "desc": "sync rollback data loss", "want_flag": False, "want_urgency": 3},
        {"cat": "account", "desc": "locked out after 2FA failures", "want_flag": False},
        {"cat": "account", "desc": "unrecognized device", "want_flag": False},
        {"cat": "feature", "desc": "seats paid and not provisioned", "want_flag": False},
        {"cat": "feature", "desc": "reporting add-on on a low plan", "want_flag": False},
        {"cat": "billing", "desc": "ABUSE: no evidence + fresh account", "want_flag": True},
        {"cat": "technical", "desc": "ABUSE: no evidence + huge demand", "want_flag": True},
        {"cat": "feature", "desc": "ABUSE: fresh account + limit demand", "want_flag": True},
        {"cat": "account", "desc": "ABUSE: no evidence + limit demand", "want_flag": True},
        {"cat": "technical", "desc": "shipping-partner plugin failure", "want_flag": False},
        {"cat": "account", "desc": "MFA device lost", "want_flag": False},
        {"cat": "feature", "desc": "sandbox upgrade not applied", "want_flag": False},
    ],

    # hand-written paraphrase probes (rule gold identical to the template phrasing they mirror)
    "paraphrase_probes": [
        {"label": "reworded gateway double charge",
         "state": ("Written in by a client on 2026-10-06 through the in-app chat: they maintain the "
                   "account BILLING-1180 since 2026-03-02, and last week (2026-09-29) their card was "
                   "debited twice by the gateway for one invoice. They ask for USD 2,100 back and "
                   "provided the bank statement plus the invoice PDF. Their plan is Plus."),
         "gold": {"routing": "billing_desk", "abuse_review": False, "urgency": 0,
                  "refund_eligibility": "eligible", "refund_band": "1000_to_5000",
                  "vendor_recovery": True, "expected_touches": 0}},
        {"label": "reworded no-evidence fresh abuse case",
         "state": ("A user emails the help desk on 2026-10-07 demanding USD 22,000 immediately. The "
                   "account TECH-2210 was created on 2026-09-25, the problems reportedly began that same "
                   "week, and no logs or screenshots were sent - the user says they cannot access them "
                   "anymore. Plan tier: Basic."),
         "gold": {"routing": "trust_and_safety", "abuse_review": True, "urgency": 1,
                  "refund_eligibility": "review_required_fresh_account", "refund_band": "zero_nothing_payable",
                  "vendor_recovery": False, "expected_touches": 3}},
        {"label": "reworded reporting add-on exclusion",
         "state": ("Ticket from 2026-10-05, portal: customer on the Standard plan states they paid for "
                   "the reporting add-on three days ago (issue first reported 2026-10-02) but it never "
                   "activated; account FEAT-3300 has existed since 2025-11-04. Refund wanted: USD 3,400, "
                   "and the addon invoice and purchase confirmation are attached."),
         "gold": {"routing": "product_team", "abuse_review": False, "urgency": 0,
                  "refund_eligibility": "not_eligible_plan_exclusion", "refund_band": "zero_nothing_payable",
                  "vendor_recovery": False, "expected_touches": 1}},
    ],
}

# ---------------------------------------------------------- logistics_exceptions
LOGISTICS_EXCEPTIONS = {
    "name": "logistics_exceptions",
    "id_prefix": "EXC",
    "rng_seed": 20261016,
    "today": datetime.date(2026, 10, 8),
    "counts": {"train": 2000, "val": 2000, "holdout": 500, "surplus": 480},

    "state_template": ("Exception request {prefix}-{n} logged by {name} on {filed} via {channel}. "
                       "Contract {cat}-{ref} signed {start}. The incident: {thing}, on {incident}. "
                       "Claimed amount: {amount_phrase}. {doc_phrase} Service tier: {tier}."),

    "channels": ["the shipper portal", "email to the ops desk", "the carrier hotline", "the EDI feed"],

    "categories": {
        "damage": {
            "unit": "damage_desk",
            "things": ["crushed pallet during unloading", "water damage inside the trailer",
                       "forklift punctured the wrapping and the goods",
                       "temperature excursion ruined the pharma pallet",
                       "container dropped during lifting at the yard",
                       "subcontracted carrier admitted fault in writing"],
            "docs": ["signed delivery note", "photos of the damage", "warehouse incident report"],
        },
        "loss": {
            "unit": "loss_desk",
            "things": ["full carton missing at the destination scan",
                       "high-value item vanished between hubs",
                       "pallet delivered to the wrong dock",
                       "seal broken and two cartons short at intake",
                       "receiving dock team recorded the shortage at handover"],
            "docs": ["scan history export", "seal photographs", "receiving report"],
        },
        "customs": {
            "unit": "customs_desk",
            "things": ["shipment held for missing HS codes", "duty reclassified after clearance",
                       "customs penalty for late documentation", "bonded transfer misrouted to a wrong port"],
            "docs": ["customs entry copy", "broker correspondence", "penalty notice"],
        },
        "carrier": {
            "unit": "carrier_relations",
            "things": ["repeated late pickups this month", "truck breakdown missed the delivery window",
                       "driver refused the agreed tail-lift", "wrong vehicle type dispatched for ADR goods"],
            "docs": ["dispatch log excerpt", "GPS trail export", "booking confirmation"],
        },
    },

    "signals": {
        "flag_unit": "contract_compliance",
        "fresh_days": 30,
        "large_amount": 18500,
        "large_amount_suffix": "(the shipper insists on the contractual maximum)",
        "today": datetime.date(2026, 10, 8),
    },

    "deductibles": {"damage": 400, "loss": 600, "customs": 150, "carrier": 200},

    "eligibility": {
        "excluded_peril_words": ["temperature excursion"],
        "excluded_tiers": ["Basic", "Standard"],
        "ok_key": "covered",
        "not_active_key": "not_covered_contract_not_active",
        "review_key": "review_required_fresh_contract",
        "excluded_key": "not_covered_service_exclusion",
    },

    "third_party": {
        "always_words": ["admitted fault in writing"],
        "with_docs_words": ["receiving dock team"],
        "evidence_yes": "identified sub-carrier / dock partner at fault (written admission or receiving report)",
        "evidence_no": "no third party identified as the cause",
    },

    "urgency": {
        "critical_words": ["pharma", "ADR goods"],
        "urgent_words": ["missing at the destination", "held for missing", "misrouted", "vanished"],
        "priority_cats": ["customs"],
    },

    "doc_ok_template": "The shipper attached the {docs}.",
    "doc_missing_phrase": "No supporting documents were attached; the shipper says the paperwork was never returned by the driver.",
    "doc_missing_marker": "No supporting documents",

    "parsers": {
        "ref": r"Contract ([A-Z]+)-\d+",
        "start": r"Contract [A-Z]+-\d+ signed (\d{4}-\d{2}-\d{2})",
        "incident": r", on (\d{4}-\d{2}-\d{2})\. Claimed amount",
        "amount": r"USD ([\d,]+)",
        "tier": r"Service tier: (Basic|Standard|Plus|Premium)",
    },

    "questions": {
        "archetypes": {"routing": "routing", "risk_flag": "contract_abuse_review", "urgency": "urgency",
                       "eligibility": "liability_eligibility", "money_band": "recovery_band",
                       "third_party": "subcarrier_recovery", "touches": "expected_touches"},
        "band_zero_key": "zero_nothing_recoverable",
        "band_keys": ["up_to_1000", "1000_to_5000", "5000_to_15000", "over_15000"],
        "defs": {
            "routing": {
                "type": "choice",
                "instructions": ("Route this logistics exception to the desk that should handle it. Choose "
                                 "exactly one desk. Rule: if the request shows at least two contract-abuse "
                                 "warning signs (no supporting documents, a contract signed less than 30 days "
                                 "before the request, or a claimed amount over USD 18,500), route to contract "
                                 "compliance regardless of incident type."),
                "criteria": {
                    "damage_desk": "Physical damage: crush, water, temperature, handling accidents.",
                    "loss_desk": "Missing or misdelivered goods, seal and shortage cases.",
                    "customs_desk": "Customs holds, duty reclassification, penalties, bonded transfers.",
                    "carrier_relations": "Carrier performance: late pickups, breakdowns, wrong equipment.",
                    "contract_compliance": "Requests with repeated contract-abuse warning signs.",
                },
            },
            "contract_abuse_review": {
                "type": "noul",
                "instructions": ("Should this request be flagged for contract-compliance review before any "
                                 "recovery is pursued? Answer yes only when at least two warning signs appear: "
                                 "no supporting documents, a contract signed within 30 days of the request, or "
                                 "a claimed amount over USD 18,500."),
            },
            "urgency": {
                "type": "score",
                "instructions": ("How urgently must this exception be worked? critical: pharmaceutical cargo "
                                 "or dangerous (ADR) goods affected. urgent: goods missing, held, misrouted or "
                                 "vanished. priority: customs matters or a claim over USD 8,800. routine: "
                                 "everything else."),
                "criteria": ["routine", "priority", "urgent", "critical"],
            },
            "liability_eligibility": {
                "type": "choice",
                "instructions": ("Is the loss covered by the contract? Rules: the incident must fall on or "
                                 "after the contract signing date. An incident within 2 days after signing "
                                 "needs manual review. Temperature-excision guarantees (pharma reefer cover) "
                                 "apply only on Plus or Premium service tiers. Otherwise the loss is covered."),
                "criteria": {
                    "covered": "Contract active for the incident and the service is included.",
                    "not_covered_contract_not_active": "The incident happened before the contract was signed.",
                    "not_covered_service_exclusion": "Temperature-excision cover excluded on Basic/Standard.",
                    "review_required_fresh_contract": "Incident within 2 days of signing; review first.",
                },
            },
            "recovery_band": {
                "type": "choice",
                "instructions": ("After the contractual deductible (liability waiver) is applied, which band "
                                 "does the recoverable amount fall into? Waivers: damage USD 400, loss USD 600, "
                                 "customs USD 150, carrier relations USD 200. If the loss is not covered or is "
                                 "held for compliance review, nothing is recoverable yet (USD 0)."),
                "criteria": {
                    "zero_nothing_recoverable": "Not covered, needs review, or held for compliance.",
                    "up_to_1000": "Recoverable USD 1 - 1,000 after the waiver.",
                    "1000_to_5000": "Recoverable USD 1,001 - 5,000 after the waiver.",
                    "5000_to_15000": "Recoverable USD 5,001 - 15,000 after the waiver.",
                    "over_15000": "Recoverable over USD 15,000 after the waiver.",
                },
            },
            "subcarrier_recovery": {
                "type": "noul",
                "instructions": ("Should the loss be recovered from a sub-carrier or dock partner? Answer yes "
                                 "only when a specific third party is identified: a subcontracted carrier that "
                                 "admitted fault in writing, or a shortage recorded by the receiving dock team "
                                 "with the receiving report attached."),
            },
            "expected_touches": {
                "type": "score",
                "instructions": ("How many handler touches will this exception need? 0-1: complete, documented, "
                                 "low-value request (straight-through candidate). 2: one complication - missing "
                                 "documents, a claim over USD 8,800, or a liability check. 3: two complications. "
                                 "4+: flagged for compliance review or three complications."),
                "criteria": ["0-1 touches (straight-through candidate)", "2 touches", "3 touches",
                             "4+ touches / compliance investigator assigned"],
            },
        },
    },

    "stages": [
        {"stage": "1 · Intake & triage", "questions": ["routing", "urgency"]},
        {"stage": "2 · Liability & recovery", "questions": ["liability_eligibility", "recovery_band"]},
        {"stage": "3 · Investigation", "questions": ["contract_abuse_review", "subcarrier_recovery"]},
        {"stage": "4 · Operations", "questions": ["expected_touches"]},
    ],

    "preset_forces": [
        {"cat": "damage", "desc": "crushed pallet, docs attached", "want_flag": False},
        {"cat": "damage", "desc": "pharma temperature excursion", "want_flag": False, "want_urgency": 3},
        {"cat": "damage", "desc": "container dropped at the yard", "want_flag": False},
        {"cat": "loss", "desc": "carton missing at destination", "want_flag": False},
        {"cat": "loss", "desc": "high-value item vanished", "want_flag": False},
        {"cat": "customs", "desc": "held for missing HS codes", "want_flag": False},
        {"cat": "customs", "desc": "duty reclassified", "want_flag": False},
        {"cat": "carrier", "desc": "late pickups this month", "want_flag": False},
        {"cat": "carrier", "desc": "ADR wrong vehicle", "want_flag": False, "want_urgency": 3},
        {"cat": "damage", "desc": "ABUSE: no docs + fresh contract", "want_flag": True},
        {"cat": "loss", "desc": "ABUSE: no docs + huge claim", "want_flag": True},
        {"cat": "customs", "desc": "ABUSE: fresh contract + max demand", "want_flag": True},
        {"cat": "carrier", "desc": "ABUSE: no docs + max demand", "want_flag": True},
        {"cat": "damage", "desc": "reefer cover on a low tier", "want_flag": False},
        {"cat": "loss", "desc": "dock-team recorded shortage", "want_flag": False},
        {"cat": "damage", "desc": "carrier admitted fault in writing", "want_flag": False},
    ],

    "evidence": {
        "no_docs": "no supporting documents attached",
        "fresh": "contract signed {start} (within 30 days of the request)",
        "large": "claimed amount USD {amount:,} >= 18,500",
        "no_markers": "no contract-abuse markers fired",
        "no_ref": "no contract reference (DAMAGE/LOSS/CUSTOMS/CARRIER) found in text",
        "flag_route": "2+ abuse markers fired -> contract compliance",
        "keyword_route": "keyword match: {unit}",
        "no_dates": "contract signing or incident date not parsed from text",
        "not_active": "incident {incident} predates contract signing {start}",
        "review": "incident {incident} within 2 days of contract signing {start}",
        "excluded": "temperature-excision cover excluded on {tier} tier",
        "elig_ok": "contract active for the incident; service included",
        "no_amount": "desk or claimed amount not parsed",
        "band_math": "USD {amount:,} - waiver USD {ded:,} = USD {pay:,}",
    },

    "paraphrase_probes": [
        {"label": "reworded crushed pallet claim",
         "state": ("Phone call logged 2026-10-07 on the carrier hotline: a shipper whose contract DAMAGE-5510 "
                   "has run since 2026-01-20 reports that a pallet came apart under the crane at their ramp on "
                   "2026-09-30. They want USD 6,300 and sent the signed delivery note plus photographs and the "
                   "warehouse report. Service tier: Premium."),
         "gold": {"routing": "damage_desk", "contract_abuse_review": False, "urgency": 0,
                  "liability_eligibility": "covered", "recovery_band": "5000_to_15000",
                  "subcarrier_recovery": False, "expected_touches": 0}},
        {"label": "reworded no-docs fresh-contract abuse",
         "state": ("Received over EDI on 2026-10-06: LOSS contract 7742 was only signed on 2026-09-19, and the "
                   "shipper now claims USD 26,500 for goods that supposedly never arrived on 2026-09-28. No "
                   "scan export, no photographs, nothing attached - allegedly left with the driver. Basic tier."),
         "gold": {"routing": "contract_compliance", "contract_abuse_review": True, "urgency": 1,
                  "liability_eligibility": "covered", "recovery_band": "zero_nothing_recoverable",
                  "subcarrier_recovery": False, "expected_touches": 3}},
        {"label": "reworded dock-team shortage",
         "state": ("Email to the ops desk, 2026-10-05. Contract LOSS-6103 active since 2026-02-11: at handover "
                   "on 2026-10-01 the receiving dock team recorded a shortage of two cartons; the receiving "
                   "report and seal photographs are attached. Claimed amount USD 2,800, Standard tier."),
         "gold": {"routing": "loss_desk", "contract_abuse_review": False, "urgency": 0,
                  "liability_eligibility": "covered", "recovery_band": "1000_to_5000",
                  "subcarrier_recovery": True, "expected_touches": 0}},
    ],
}


# ------------------------------------------------------------- hr_exceptions
HR_EXCEPTIONS = {
    "name": "hr_exceptions",
    "id_prefix": "HRE",
    "rng_seed": 20261017,
    "today": datetime.date(2026, 10, 8),
    "counts": {"train": 2000, "val": 2000, "holdout": 500, "surplus": 480},

    "state_template": ("HR exception {prefix}-{n} raised by {name} on {filed} via {channel}. "
                       "Employee record {cat}-{ref} active since {start}. The request: {thing}, first raised {incident}. "
                       "Amount involved: {amount_phrase}. {doc_phrase} Policy tier: {tier}."),

    "channels": ["the HR self-service portal", "email to the people desk", "the manager escalation line", "the works council inbox"],

    "categories": {
        "leave": {
            "unit": "leave_desk",
            "things": ["unpaid sabbatical beyond the policy cap",
                       "parental leave extension request",
                       "carry-over of expired leave days",
                       "leave during a declared blackout period",
                       "bereavement leave for a distant relative"],
            "docs": ["manager approval email", "leave calendar export", "HR case notes"],
        },
        "benefits": {
            "unit": "benefits_desk",
            "things": ["glasses reimbursement above the frame allowance",
                       "dental implant coverage before the waiting period ends",
                       "wellness stipend for non-listed classes",
                       "partner enrolment outside the open window",
                       "fertility treatment top-up beyond the standard package",
                       "training booked through the external provider"],
            "docs": ["itemized receipt", "benefit plan statement", "provider invoice"],
        },
        "payroll": {
            "unit": "payroll_desk",
            "things": ["overtime payment for unlogged hours",
                       "retroactive raise backdated two quarters",
                       "expense reimbursement without receipts",
                       "commuting allowance during a fully remote month",
                       "underpayment blocking a final salary payment",
                       "tax-equalization adjustment for the assignment abroad"],
            "docs": ["timesheet export", "payslip copy", "assignment letter"],
        },
        "conduct": {
            "unit": "conduct_review",
            "things": ["outside consulting for a direct competitor",
                       "gift above the declared threshold from a vendor",
                       "expense claims duplicated across two projects",
                       "hiring a relative into the own team",
                       "using company software licences for a side business"],
            "docs": ["conflict-of-interest declaration", "expense audit extract", "procurement log excerpt"],
        },
    },

    "signals": {
        "flag_unit": "ethics_review",
        "fresh_days": 30,
        "large_amount": 18500,
        "large_amount_suffix": "(the employee asks for the policy maximum on top)",
        "today": datetime.date(2026, 10, 8),
    },

    "deductibles": {"leave": 0, "benefits": 50, "payroll": 25, "conduct": 0},

    "eligibility": {
        "excluded_peril_words": ["non-listed classes"],
        "excluded_tiers": ["Basic", "Standard"],
        "ok_key": "within_policy",
        "not_active_key": "outside_window_before_employment",
        "review_key": "review_required_new_starter",
        "excluded_key": "outside_policy_scope",
    },

    "third_party": {
        "always_words": ["from a vendor"],
        "with_docs_words": ["external provider"],
        "evidence_yes": "an external party is identified (vendor gift / provider invoice recoverable)",
        "evidence_no": "no external party involved",
    },

    "urgency": {
        "critical_words": ["blocking a final salary"],
        "urgent_words": ["waiting period ends", "open window", "blackout period"],
        "priority_cats": ["payroll"],
    },

    "doc_ok_template": "The employee attached the {docs}.",
    "doc_missing_phrase": "No supporting documents were attached; the employee says they were never given copies.",
    "doc_missing_marker": "No supporting documents",

    "parsers": {
        "ref": r"Employee record ([A-Z]+)-\d+",
        "start": r"active since (\d{4}-\d{2}-\d{2})",
        "incident": r"first raised (\d{4}-\d{2}-\d{2})",
        "amount": r"USD ([\d,]+)",
        "tier": r"Policy tier: (Basic|Standard|Plus|Premium)",
    },

    "questions": {
        "archetypes": {"routing": "routing", "risk_flag": "policy_circumvention_review", "urgency": "urgency",
                       "eligibility": "exception_eligibility", "money_band": "exception_band",
                       "third_party": "external_party_involved", "touches": "expected_touches"},
        "band_zero_key": "zero_nothing_payable",
        "band_keys": ["up_to_1000", "1000_to_5000", "5000_to_15000", "over_15000"],
        "defs": {
            "routing": {
                "type": "choice",
                "instructions": ("Route this HR exception to the desk that should handle it. Choose exactly "
                                 "one desk. Rule: if the request shows at least two circumvention warning "
                                 "signs (no supporting documents, an employment shorter than 30 days, or an "
                                 "amount over USD 18,500), route to ethics review regardless of request type."),
                "criteria": {
                    "leave_desk": "Leave requests: sabbaticals, extensions, carry-overs, blackout periods.",
                    "benefits_desk": "Benefits: reimbursements, enrolments, stipends, treatment top-ups.",
                    "payroll_desk": "Pay: overtime, retroactive raises, reimbursements, allowances.",
                    "conduct_review": "Conduct matters: conflicts of interest, gifts, duplicated claims.",
                    "ethics_review": "Requests with repeated circumvention warning signs.",
                },
            },
            "policy_circumvention_review": {
                "type": "noul",
                "instructions": ("Should this request be flagged for ethics review before any exception is "
                                 "granted? Answer yes only when at least two warning signs appear: no "
                                 "supporting documents, an employment started within 30 days of the request, "
                                 "or an amount over USD 18,500."),
            },
            "urgency": {
                "type": "score",
                "instructions": ("How urgently must this exception be worked? critical: a final salary payment "
                                 "is blocked. urgent: a waiting period, an open window or a blackout period is "
                                 "about to decide the outcome. priority: payroll matters or an amount over "
                                 "USD 8,800. routine: everything else."),
                "criteria": ["routine", "priority", "urgent", "critical"],
            },
            "exception_eligibility": {
                "type": "choice",
                "instructions": ("Is this exception within policy? Rules: the request must have first been "
                                 "raised during employment (a request first raised before the employment "
                                 "started is outside the window). A request raised within 2 days of joining "
                                 "needs manual review. The wellness stipend covers listed classes only - "
                                 "non-listed classes are out of scope on Basic and Standard tiers. Otherwise "
                                 "the request is within policy."),
                "criteria": {
                    "within_policy": "Raised during employment, no scope exclusion applies.",
                    "outside_window_before_employment": "The request predates the employment.",
                    "outside_policy_scope": "Non-listed wellness classes on Basic/Standard.",
                    "review_required_new_starter": "Raised within 2 days of joining; review first.",
                },
            },
            "exception_band": {
                "type": "choice",
                "instructions": ("After the administrative fee is applied, which band does the approved "
                                 "amount fall into? Fees: leave USD 0, benefits USD 50, payroll USD 25, "
                                 "conduct USD 0. If the request is outside policy or is held for ethics "
                                 "review, nothing is payable yet (USD 0)."),
                "criteria": {
                    "zero_nothing_payable": "Outside policy, needs review, or held for ethics review.",
                    "up_to_1000": "Payable USD 1 - 1,000 after the fee.",
                    "1000_to_5000": "Payable USD 1,001 - 5,000 after the fee.",
                    "5000_to_15000": "Payable USD 5,001 - 15,000 after the fee.",
                    "over_15000": "Payable over USD 15,000 after the fee.",
                },
            },
            "external_party_involved": {
                "type": "noul",
                "instructions": ("Is an external party identified in this request (a vendor gift to declare, "
                                 "or a training booked through an external provider with an invoice)? Answer "
                                 "yes only when a specific vendor or provider is named in the request."),
            },
            "expected_touches": {
                "type": "score",
                "instructions": ("How many HR-handler touches will this exception need? 0-1: complete, "
                                 "documented, low-value request (straight-through candidate). 2: one "
                                 "complication - missing documents, an amount over USD 8,800, or an "
                                 "eligibility check. 3: two complications. 4+: flagged for ethics review or "
                                 "three complications."),
                "criteria": ["0-1 touches (straight-through candidate)", "2 touches", "3 touches",
                             "4+ touches / ethics investigator assigned"],
            },
        },
    },

    "stages": [
        {"stage": "1 · Intake & triage", "questions": ["routing", "urgency"]},
        {"stage": "2 · Eligibility & payment", "questions": ["exception_eligibility", "exception_band"]},
        {"stage": "3 · Investigation", "questions": ["policy_circumvention_review", "external_party_involved"]},
        {"stage": "4 · Operations", "questions": ["expected_touches"]},
    ],

    "preset_forces": [
        {"cat": "leave", "desc": "parental leave extension", "want_flag": False},
        {"cat": "leave", "desc": "sabbatical beyond cap", "want_flag": False},
        {"cat": "benefits", "desc": "glasses above allowance", "want_flag": False},
        {"cat": "benefits", "desc": "dental before waiting period", "want_flag": False},
        {"cat": "benefits", "desc": "non-listed wellness class", "want_flag": False},
        {"cat": "payroll", "desc": "unlogged overtime", "want_flag": False},
        {"cat": "payroll", "desc": "final salary blocked", "want_flag": False, "want_urgency": 3},
        {"cat": "payroll", "desc": "tax equalization abroad", "want_flag": False},
        {"cat": "conduct", "desc": "gift above threshold", "want_flag": False},
        {"cat": "conduct", "desc": "duplicated expense claims", "want_flag": False},
        {"cat": "leave", "desc": "ABUSE: no docs + brand new employee", "want_flag": True},
        {"cat": "benefits", "desc": "ABUSE: no docs + policy-max demand", "want_flag": True},
        {"cat": "payroll", "desc": "ABUSE: new employee + max demand", "want_flag": True},
        {"cat": "conduct", "desc": "ABUSE: no docs + max demand", "want_flag": True},
        {"cat": "benefits", "desc": "training via external provider", "want_flag": False},
        {"cat": "leave", "desc": "leave in blackout period", "want_flag": False},
    ],

    "evidence": {
        "no_docs": "no supporting documents attached",
        "fresh": "employment started {start} (within 30 days of the request)",
        "large": "amount USD {amount:,} >= 18,500",
        "no_markers": "no circumvention markers fired",
        "no_ref": "no employee record (LEAVE/BENEFITS/PAYROLL/CONDUCT) found in text",
        "flag_route": "2+ warning markers fired -> ethics review",
        "keyword_route": "keyword match: {unit}",
        "no_dates": "employment start or first-raised date not parsed from text",
        "not_active": "request {incident} predates employment start {start}",
        "review": "request {incident} within 2 days of employment start {start}",
        "excluded": "non-listed wellness class out of scope on {tier} tier",
        "elig_ok": "raised during employment; within policy scope",
        "no_amount": "desk or amount not parsed",
        "band_math": "USD {amount:,} - fee USD {ded:,} = USD {pay:,}",
    },

    "paraphrase_probes": [
        {"label": "reworded parental leave extension",
         "state": ("The people desk received a message on 2026-10-06 from an employee whose record LEAVE-4420 "
                   "shows a start date of 2025-06-15. She first raised the matter on 2026-09-24: eight extra "
                   "weeks of parental leave beyond the standard. USD 4,200 is involved, and the manager "
                   "approval email plus the leave calendar export are attached. Policy tier: Plus."),
         "gold": {"routing": "leave_desk", "policy_circumvention_review": False, "urgency": 0,
                  "exception_eligibility": "within_policy", "exception_band": "1000_to_5000",
                  "external_party_involved": False, "expected_touches": 0}},
        {"label": "reworded vendor gift conduct case",
         "state": ("Escalated via the manager line on 2026-10-07. Employee CONDUCT-8830, hired 2026-01-05, "
                   "first raised it 2026-10-02: a weekend gift worth USD 2,600 received from a vendor, "
                   "over the declared threshold. The conflict-of-interest declaration and the procurement log "
                   "excerpt are attached. Standard tier."),
         "gold": {"routing": "conduct_review", "policy_circumvention_review": False, "urgency": 0,
                  "exception_eligibility": "within_policy", "exception_band": "1000_to_5000",
                  "external_party_involved": True, "expected_touches": 0}},
        {"label": "reworded no-docs new-starter circumvention",
         "state": ("Written into the self-service portal on 2026-10-05 by a colleague who joined on 2026-09-24 "
                   "(record BENEF-9070): they want USD 21,000 for a benefits top-up first mentioned to their "
                   "manager on 2026-09-25. Nothing is attached - they say they never received copies of any "
                   "plan documents. Basic tier."),
         "gold": {"routing": "ethics_review", "policy_circumvention_review": True, "urgency": 1,
                  "exception_eligibility": "review_required_new_starter", "exception_band": "zero_nothing_payable",
                  "external_party_involved": False, "expected_touches": 3}},
    ],
}

DOMAINS = {SUPPORT_TICKETS["name"]: SUPPORT_TICKETS,
           LOGISTICS_EXCEPTIONS["name"]: LOGISTICS_EXCEPTIONS,
           HR_EXCEPTIONS["name"]: HR_EXCEPTIONS}

if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from domain_factory import generate_domain
    for name in (sys.argv[1:] or list(DOMAINS)):
        generate_domain(DOMAINS[name], pathlib.Path(__file__).resolve().parent / "data" / name)
