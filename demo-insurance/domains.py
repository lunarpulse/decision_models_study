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

DOMAINS = {SUPPORT_TICKETS["name"]: SUPPORT_TICKETS}

if __name__ == "__main__":
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from domain_factory import generate_domain
    for name in (sys.argv[1:] or list(DOMAINS)):
        generate_domain(DOMAINS[name], pathlib.Path(__file__).resolve().parent / "data" / name)
