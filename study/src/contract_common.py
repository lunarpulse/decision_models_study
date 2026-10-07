"""Shared fixtures for G1 contract tests (plan §4). Subject-agnostic."""
import os as _os, pathlib as _pl
_STUDY_ROOT = _pl.Path(_os.environ.get("DECISION_STUDY_ROOT", _pl.Path(__file__).resolve().parents[1]))
_ANCHOR = _pl.Path(_os.environ.get("CLM8B_ANCHOR_ROOT", _STUDY_ROOT / "anchor-corpus"))
_MODELS = _pl.Path(_os.environ.get("DECIDER_MODELS_DIR", _STUDY_ROOT / "models"))

import json, time, pathlib

RUN_ROOT = pathlib.Path(str(_STUDY_ROOT / "g0-20261007"))

STATES = [
    {"ticket_id": "TCK-8821", "subject": "System downtime and billing dispute",
     "body": "Our production API has been failing since 6 AM. We lost critical transactions. We demand an immediate SLA refund."},
    {"body": "I was charged twice for the same purchase last week and would like the duplicate charge reversed."},
    {"body": "Security alert: unexpected IAM key creation from an unrecognized geographic region at 03:14 UTC."},
    {"body": "How do I export my invoice history to CSV? Just looking for the steps."},
    {"body": "This is unacceptable — cancel my account immediately or I will escalate to my company's procurement team."},
]

# Identical semantic schema across subjects: 4-way choice, 4-level score, noul.
CHOICE_OPTS = ["infrastructure", "billing", "security", "support"]
SCORE_LEVELS = ["low priority", "medium", "high priority", "critical blocker"]


def shuffle_probe_states():
    return STATES


def dump(subject: str, payload: dict):
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    out = RUN_ROOT / f"contract-{subject}.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[ledger] wrote {out}")


class Timer:
    def __init__(self): self.t0 = None
    def __enter__(self):
        self.t0 = time.perf_counter(); return self
    def __exit__(self, *a):
        self.ms = (time.perf_counter() - self.t0) * 1000.0
