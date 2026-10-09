"""Synthetic TrustShield world: customers with 90-day histories, beneficiaries, scam campaigns,
hashed indicators and past victim links. Deterministic (seeded) so demos are repeatable."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import numpy as np

from ..core.privacy import indicator_hash, mask
from ..core.store import store

COLLS = ["ts_customers", "ts_beneficiaries", "ts_indicators", "ts_campaigns", "ts_victim_links",
         "ts_assessments", "ts_payments", "ts_cases", "ts_evidence", "ts_eval_runs"]

# --------------------------------------------------------------------------- demo customers
DEMO_CUSTOMERS = [
    {"customer_id": "c_priya", "name": "Priya Sharma", "age_band": "55-64", "language": "en", "vulnerable": False,
     "city": "Bengaluru", "segment": "salaried", "balance": 420000,
     "payees": [  # ben_id, name, account, typical amount, cadence days, hour
         ("b_kapoor", "Mr. S. Kapoor (Landlord)", "112233445566", 25000, 30, 10),
         ("b_citypower", "City Power Ltd", "900100200300", 2600, 30, 19),
         ("b_aarav", "Aarav Sharma (Son)", "602211887766", 18500, 90, 20),
         ("b_freshmart", "FreshMart Groceries", "771100224466", 2800, 5, 18),
         ("b_sip", "BlueLeaf Mutual Fund SIP", "445566778899", 10000, 30, 9),
     ]},
    {"customer_id": "c_meena", "name": "Meena Iyer", "age_band": "70+", "language": "hi", "vulnerable": True,
     "city": "Chennai", "segment": "retiree", "balance": 980000,
     "payees": [
         ("b_meena_pharmacy", "Apollo-Care Pharmacy", "331122009988", 3200, 15, 11),
         ("b_meena_daughter", "Kavya Iyer (Daughter)", "556677001122", 15000, 60, 17),
         ("b_meena_maid", "Lakshmi (Home help)", "668800112233", 6000, 30, 9),
     ]},
    {"customer_id": "c_arjun", "name": "Arjun Rao", "age_band": "25-34", "language": "en", "vulnerable": False,
     "city": "Hyderabad", "segment": "young_professional", "balance": 110000,
     "payees": [
         ("b_arjun_rent", "Sai Residency PG", "223344556677", 14000, 30, 22),
         ("b_arjun_food", "Swiggo Wallet", "889900112244", 650, 2, 21),
         ("b_arjun_friend", "Nikhil (Friend)", "445500661122", 1500, 12, 23),
     ]},
]

# --------------------------------------------------------------------------- scam campaigns
CAMPAIGNS = [
    {"campaign_id": "C-17", "label": "Fake KYC-block / bank impersonation", "scam_type": "bank_impersonation",
     "indicators": [("url_domain", "trustbank-kyc-verify.in"), ("url_domain", "tb-secure-update.co"),
                    ("phone", "+91 87654 21098"), ("phone", "+91 70123 45690"),
                    ("account", "50100234567821"), ("account", "50100988776655")],
     "victims": 41, "banks": ["TrustBank", "Bank B"]},
    {"campaign_id": "C-22", "label": "Parcel redelivery fee phishing", "scam_type": "parcel_delivery",
     "indicators": [("url_domain", "parcel-redeliver-in.top"), ("phone", "+91 90011 22334")],
     "victims": 126, "banks": ["TrustBank"]},
    {"campaign_id": "C-31", "label": "Task-based 'like videos' job scam", "scam_type": "job_task",
     "indicators": [("upi", "starmedia.tasks@okpay"), ("account", "30441122998877"), ("phone", "+91 81234 56789")],
     "victims": 58, "banks": ["TrustBank", "Bank C"]},
    {"campaign_id": "C-08", "label": "Guaranteed-return AI trading fund", "scam_type": "investment",
     "indicators": [("account", "36920011774410"), ("url_domain", "alphagrowth-ai.top")],
     "victims": 23, "banks": ["Bank B"]},
]

# Pre-registered "new payee" suggestions the demo UI offers (one mule, one genuine)
SUGGESTED_PAYEES = [
    {"display_name": "RK Traders", "account": "50100234567821", "bank_code": "PAYB", "hint": "from the KYC message"},
    {"display_name": "Secure Wallet Services", "account": "36920011774410", "bank_code": "NWLT", "hint": "from the investment message"},
    {"display_name": "Rohan Mehta", "account": "918020045566", "bank_code": "HDFX", "hint": "new landlord (genuine)"},
    {"display_name": "StarMedia Tasks", "account": "starmedia.tasks@okpay", "bank_code": "UPI", "hint": "from the job offer"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_history(rng: random.Random, payees: list[tuple], days: int = 90) -> list[dict]:
    """Recurring payments per payee with amount noise + timing jitter."""
    txns: list[dict] = []
    start = _now() - timedelta(days=days)
    for ben_id, _name, _acct, typical, cadence, hour in payees:
        t = start + timedelta(days=rng.uniform(0, cadence))
        while t < _now():
            amt = max(50.0, rng.gauss(typical, typical * 0.12))
            txns.append({"ben_id": ben_id, "amount": round(amt, 2),
                         "ts": (t.replace(hour=max(0, min(23, hour + rng.randint(-1, 1))))).isoformat()})
            t += timedelta(days=cadence * rng.uniform(0.9, 1.1))
    txns.sort(key=lambda x: x["ts"])
    return txns


def compute_stats(txns: list[dict], balance: float) -> dict:
    amounts = np.array([t["amount"] for t in txns]) if txns else np.array([1000.0])
    hours = np.array([datetime.fromisoformat(t["ts"]).hour for t in txns]) if txns else np.array([12])
    return {
        "mean_90d": float(amounts.mean()), "std_90d": float(max(amounts.std(), amounts.mean() * 0.25, 500)),
        "max_90d": float(amounts.max()), "txn_count_90d": int(len(amounts)),
        "p05_hour": int(np.percentile(hours, 5)), "p95_hour": int(np.percentile(hours, 95)),
        "balance": float(balance),
    }


def seed(force: bool = False) -> dict:
    s = store()
    if not force and s.count("ts_customers") > 0:
        return {"seeded": False}
    s.clear(COLLS)
    rng = random.Random(42)
    history_rows: list[dict] = []
    for c in DEMO_CUSTOMERS:
        txns = build_history(rng, c["payees"])
        for t in txns:
            history_rows.append({"customer_id": c["customer_id"], **t})
        doc = {k: v for k, v in c.items() if k != "payees"}
        doc["stats"] = compute_stats(txns, c["balance"])
        doc["devices"] = [{"id": "d_primary", "first_seen": (_now() - timedelta(days=400)).isoformat()}]
        s.set("ts_customers", c["customer_id"], doc)
        for ben_id, name, acct, *_ in c["payees"]:
            paid = [t for t in txns if t["ben_id"] == ben_id]
            s.set("ts_beneficiaries", ben_id, {
                "ben_id": ben_id, "customer_id": c["customer_id"], "display_name": name,
                "account_masked": mask("account", acct), "account_hash": indicator_hash("account", acct),
                "bank_code": "TRST", "type": "bank_account",
                "added_at": (_now() - timedelta(days=rng.randint(200, 900))).isoformat(),
                "prior_payment_count": len(paid), "last_paid_at": paid[-1]["ts"] if paid else None,
                "verified_name": name.split(" (")[0],
            })

    for camp in CAMPAIGNS:
        hashes = []
        for kind, value in camp["indicators"]:
            h = indicator_hash(kind, value)
            hashes.append(h)
            s.set("ts_indicators", h, {
                "hash": h, "kind": kind, "display": mask(kind, value), "campaign_id": camp["campaign_id"],
                "confidence": round(rng.uniform(0.82, 0.95), 2), "reports": rng.randint(3, 30),
                "banks_reporting": camp["banks"],
                "first_seen": (_now() - timedelta(days=rng.randint(10, 60))).isoformat(),
                "last_seen": (_now() - timedelta(hours=rng.randint(1, 72))).isoformat(),
            })
        s.set("ts_campaigns", camp["campaign_id"], {
            "campaign_id": camp["campaign_id"], "label": camp["label"], "scam_type": camp["scam_type"],
            "indicator_hashes": hashes, "victim_count": camp["victims"], "banks_reporting": camp["banks"],
            "confidence": 0.9, "status": "active", "summary": None,
        })
        # A few synthetic past victim payments linked to indicators (for the network graph)
        for i in range(min(8, camp["victims"])):
            h = rng.choice(hashes)
            amt = rng.choice([4999, 12000, 25000, 40000, 85000, 150000])
            s.set("ts_victim_links", f"{camp['campaign_id']}-v{i}", {
                "id": f"{camp['campaign_id']}-v{i}", "campaign_id": camp["campaign_id"], "indicator_hash": h,
                "amount": amt, "bank": rng.choice(camp["banks"]),
                "days_ago": rng.randint(1, 20),
            })
    _HISTORY.clear()
    _HISTORY.extend(history_rows)
    return {"seeded": True, "customers": len(DEMO_CUSTOMERS), "campaigns": len(CAMPAIGNS)}


_HISTORY: list[dict] = []


def history_rows() -> list[dict]:
    """Synthetic transaction history (exported to BigQuery by infra/seed_bigquery.py)."""
    if not _HISTORY:
        rng = random.Random(42)
        for c in DEMO_CUSTOMERS:
            for t in build_history(rng, c["payees"]):
                _HISTORY.append({"customer_id": c["customer_id"], **t})
    return list(_HISTORY)
