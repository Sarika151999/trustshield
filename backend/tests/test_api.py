"""End-to-end API tests in offline mode (mock Gemini, in-memory store). Run: pytest -q"""
from __future__ import annotations

import os

os.environ.setdefault("GEMINI_BACKEND", "mock")
os.environ.setdefault("STORE_BACKEND", "memory")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _new_payee(client, name, account):
    r = client.post("/api/ts/beneficiaries", json={"customer_id": "c_priya", "display_name": name, "account": account})
    assert r.status_code == 200
    return r.json()["ben_id"]


def _sample(client, sample_id):
    r = client.post("/api/ts/evidence/sample", data={"customer_id": "c_priya", "sample_id": sample_id})
    return r.json()["evidence_id"]


def test_health(client):
    assert client.get("/api/health").json()["ok"]


def test_cfo_api_is_not_exposed(client):
    assert client.get("/api/cfo/summary").status_code == 404


def test_trustshield_scam_is_held_and_case_opened(client):
    ben = _new_payee(client, "RK Traders", "50100234567821")
    ev = _sample(client, "kyc_whatsapp")
    r = client.post("/api/ts/assess", json={"customer_id": "c_priya", "ben_id": ben, "amount": 85000,
                                            "note": "KYC refund", "context": {"active_call": True},
                                            "evidence_ids": [ev]}).json()
    assert r["decision"] == "HOLD"
    assert "C-17" in r["matched_campaigns"]
    assert any(s["code"] == "beneficiary_known_mule" for s in r["signals"])
    cases = client.get("/api/ts/cases?status=open").json()
    assert any(c["assessment_id"] == r["assessment_id"] for c in cases)
    g = client.get(f"/api/ts/graph/assessment/{r['assessment_id']}").json()
    assert len(g["nodes"]) > 5
    # confirmed payment on HOLD is refused
    assert client.post(f"/api/ts/payments/{r['payment_id']}/action", json={"action": "confirm"}).status_code == 409


def test_trustshield_legit_paths(client):
    rent = client.post("/api/ts/assess", json={"customer_id": "c_priya", "ben_id": "b_kapoor", "amount": 25000}).json()
    assert rent["decision"] == "PASS"
    ben = _new_payee(client, "Rohan Mehta", "918020045566")
    ev = _sample(client, "legit_landlord")
    r = client.post("/api/ts/assess", json={"customer_id": "c_priya", "ben_id": ben, "amount": 85000,
                                            "evidence_ids": [ev]}).json()
    assert r["decision"] == "PASS"


def test_trustshield_warn_escalates_on_safety_answers(client):
    ben = _new_payee(client, "Some Shop", "123456789012")
    r = client.post("/api/ts/assess", json={"customer_id": "c_priya", "ben_id": ben, "amount": 85000,
                                            "context": {"active_call": True}}).json()
    assert r["decision"] in ("WARN", "HOLD")
    if r["decision"] == "WARN":
        q = r["intervention"]["safety_questions"][0]
        out = client.post(f"/api/ts/assessments/{r['assessment_id']}/answers",
                          json={"answers": {q["id"]: q["escalate_if"]}}).json()
        assert out["final_decision"] == "HOLD"


def test_trustshield_injection_does_not_pass(client):
    ben = _new_payee(client, "RK Traders 2", "50100234567821")
    ev = _sample(client, "injection_kyc")
    r = client.post("/api/ts/assess", json={"customer_id": "c_priya", "ben_id": ben, "amount": 85000,
                                            "evidence_ids": [ev]}).json()
    assert r["decision"] == "HOLD"


def test_trustshield_eval_ablation(client):
    run = client.post("/api/ts/eval/run?n=200&live=false").json()
    assert run["results"]["full"]["recall"] >= run["results"]["behaviour_only"]["recall"]
