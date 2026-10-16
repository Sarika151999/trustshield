"""TrustShield orchestration: assessment pipeline, interventions, analyst cases, intel sharing, graph."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from ..config import settings
from ..core.events import bus
from ..core.gemini import GeminiUnavailable, gemini
from ..core.privacy import indicator_hash, mask, redact
from ..core.store import new_id, store
from ..core.util import Timer, fmt_inr, now_iso
from . import content, explain, fusion, intel
from .features import behaviour_signals
from .schemas import AssessRequest, CampaignSummary, NewBeneficiary, ShareIndicator


# =========================================================================== beneficiaries & evidence
def add_beneficiary(req: NewBeneficiary) -> dict:
    s = store()
    if not s.get("ts_customers", req.customer_id):
        raise HTTPException(404, "customer not found")
    kind = "upi" if "@" in req.account else "account"
    ben_id = new_id("b")
    doc = {
        "ben_id": ben_id, "customer_id": req.customer_id, "display_name": req.display_name,
        "account_masked": mask(kind, req.account), "account_hash": indicator_hash(kind, req.account),
        "bank_code": req.bank_code, "type": "upi" if kind == "upi" else req.type, "added_at": now_iso(),
        "prior_payment_count": 0, "last_paid_at": None, "verified_name": req.display_name,
    }
    s.set("ts_beneficiaries", ben_id, doc)
    return doc


def save_evidence(customer_id: str, kind: str, *, blob_key: str | None = None, mime: str | None = None,
                  text: str | None = None, sample_id: str | None = None) -> dict:
    ev_id = new_id("ev")
    doc = {"evidence_id": ev_id, "customer_id": customer_id, "kind": kind, "blob_key": blob_key, "mime": mime,
           "text": text, "sample_id": sample_id, "created_at": now_iso(),
           "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
    store().set("ts_evidence", ev_id, doc)
    return doc


# =========================================================================== assessment
def assess(req: AssessRequest) -> dict:
    s = store()
    t = Timer()
    profile = s.get("ts_customers", req.customer_id)
    ben = s.get("ts_beneficiaries", req.ben_id)
    if not profile or not ben or ben["customer_id"] != req.customer_id:
        raise HTTPException(404, "customer or beneficiary not found")
    evidence = [e for e in (s.get("ts_evidence", i) for i in req.evidence_ids) if e]
    t.mark("load")

    is_new = datetime.now(timezone.utc) - datetime.fromisoformat(ben["added_at"]) < timedelta(days=1)
    analysis, a_meta = content.analyze(evidence, req.amount, is_new, req.note)
    t.mark("content_analysis")

    hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    recent = [p for p in s.list("ts_payments", where={"customer_id": req.customer_id})
              if p["created_at"] >= hour_ago and p["status"] in ("completed", "pass")]
    b_sig = behaviour_signals(req.amount, ben, profile, req.context, recent_outgoing_1h=len(recent))
    c_sig = content.content_signals(analysis)
    i_sig, matches, hashes = intel.lookup(analysis, ben)
    t.mark("features_intel")

    signals = fusion.attribute(b_sig + c_sig + i_sig)
    risk, comps = fusion.score(signals)
    decision, hard_rule = fusion.decide(risk, signals, profile.get("vulnerable", False))
    behaviour_only = fusion.FusionConfig(use_content=False, use_intel=False)
    behaviour_risk, _ = fusion.score(b_sig, behaviour_only)
    behaviour_decision, _ = fusion.decide(behaviour_risk, b_sig, profile.get("vulnerable", False), behaviour_only)
    t.mark("fusion")

    iv, e_meta = explain.generate(decision, signals, analysis, profile, req.amount)
    t.mark("explanation")

    pay_id, as_id = new_id("pay"), new_id("as")
    indicators = [{"hash": indicator_hash(k, v), "kind": k, "display": mask(k, v)}
                  for k, v in intel.extract_indicators(analysis)]
    a_doc = {
        "assessment_id": as_id, "payment_id": pay_id, "customer_id": req.customer_id,
        "customer_name": profile["name"], "language": profile.get("language", "en"),
        "vulnerable": profile.get("vulnerable", False),
        "beneficiary": {"ben_id": ben["ben_id"], "display_name": ben["display_name"],
                        "account_masked": ben["account_masked"], "account_hash": ben["account_hash"],
                        "added_at": ben["added_at"], "is_new": is_new},
        "amount": req.amount, "amount_fmt": fmt_inr(req.amount), "note": req.note,
        "context": req.context.model_dump(), "evidence_ids": req.evidence_ids,
        "decision": decision, "final_decision": decision, "hard_rule": hard_rule, "risk": round(risk, 4),
        "counterfactual": {
            "behaviour_only": {"risk": round(behaviour_risk, 4), "decision": behaviour_decision},
            "full_context": {"risk": round(risk, 4), "decision": decision},
            "risk_delta": round(risk - behaviour_risk, 4),
        },
        "scores": {k: round(v, 4) for k, v in comps.items()},
        "signals": [x.model_dump() for x in signals],
        "analysis": _analysis_view(analysis),
        "indicators": indicators,
        "matched_campaigns": sorted({m["campaign_id"] for m in matches}),
        "intervention": iv.model_dump(),
        "meta": {**a_meta, **e_meta, "policy_version": fusion.POLICY_VERSION,
                 "explain_prompt": explain.PROMPT_VERSION},
        "latency_ms": {**t.marks, "total": t.total()},
        "status": "open", "created_at": now_iso(),
    }
    s.set("ts_assessments", as_id, a_doc)
    s.set("ts_payments", pay_id, {
        "payment_id": pay_id, "customer_id": req.customer_id, "ben_id": req.ben_id, "amount": req.amount,
        "note": req.note, "status": {"PASS": "pass", "WARN": "warned", "HOLD": "held"}[decision],
        "assessment_id": as_id, "created_at": now_iso(),
    })
    if decision == "HOLD":
        _open_case(a_doc, reason=hard_rule or "risk_threshold")
    bus().publish("assessment.completed", _event_view(a_doc))
    return a_doc


def _analysis_view(a) -> dict | None:
    if a is None:
        return None
    return {
        "scam_type": a.scam_type, "is_scam_likely": a.is_scam_likely, "confidence": a.confidence,
        "legitimate_context_confidence": a.legitimate_context_confidence, "payment_link": a.payment_link,
        "language": a.language, "summary": a.summary,
        "transcript_redacted": redact(a.transcript),
        "tactics": [{"name": t.name, "quote": redact(t.evidence_quote), "severity": t.severity} for t in a.tactics],
        "impersonated_org": a.entities.impersonated_org,
        "quote_accuracy": content.quote_accuracy(a),
    }


def _event_view(a: dict) -> dict:
    return {k: a[k] for k in ("assessment_id", "payment_id", "customer_id", "amount", "decision", "final_decision",
                              "risk", "scores", "hard_rule", "matched_campaigns", "created_at")} | {
        "latency_ms": a["latency_ms"]["total"], "analyzer": a["meta"].get("analyzer"),
        "scam_type": (a["analysis"] or {}).get("scam_type"),
        "signal_codes": [x["code"] for x in a["signals"]]}


def _open_case(a_doc: dict, reason: str) -> None:
    case_id = "case_" + a_doc["assessment_id"].split("_", 1)[1]
    store().set("ts_cases", case_id, {
        "case_id": case_id, "assessment_id": a_doc["assessment_id"], "customer_name": a_doc["customer_name"],
        "amount": a_doc["amount"], "risk": a_doc["risk"], "reason": reason, "status": "open",
        "scam_type": (a_doc["analysis"] or {}).get("scam_type"), "created_at": now_iso(),
        "sla_due": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
    })


def submit_answers(as_id: str, answers: dict[str, str]) -> dict:
    s = store()
    a = s.get("ts_assessments", as_id)
    if not a:
        raise HTTPException(404, "assessment not found")
    qs = {q["id"]: q for q in a["intervention"]["safety_questions"]}
    flagged = [qs[k]["text"] for k, v in answers.items() if k in qs and v == qs[k]["escalate_if"]]
    update = {"safety_answers": answers, "safety_flags": flagged}
    if flagged and a["final_decision"] != "HOLD":
        update["final_decision"] = "HOLD"
        a.update(update)
        _open_case(a, reason="safety_answers")
        s.update("ts_payments", a["payment_id"], {"status": "held"})
        iv = explain.template_intervention("HOLD", [fusion.Signal(**x) for x in a["signals"]], None,
                                           a["language"], a["amount"])
        update["intervention_escalated"] = iv.model_dump()
    s.update("ts_assessments", as_id, update)
    a.update(update)
    return {"final_decision": a["final_decision"], "flags": flagged,
            "intervention": update.get("intervention_escalated")}


def payment_action(pay_id: str, action: str) -> dict:
    s = store()
    p = s.get("ts_payments", pay_id)
    if not p:
        raise HTTPException(404, "payment not found")
    a = s.get("ts_assessments", p["assessment_id"])
    if action == "confirm":
        if a["final_decision"] == "HOLD":
            raise HTTPException(409, "payment is on hold pending review")
        status = "completed"
        s.update("ts_beneficiaries", p["ben_id"], {"prior_payment_count": 1, "last_paid_at": now_iso()})
    else:
        status = "cancelled"
    s.update("ts_payments", pay_id, {"status": status})
    s.update("ts_assessments", p["assessment_id"], {"payment_status": status})
    return {"payment_id": pay_id, "status": status}


# =========================================================================== analyst
def list_cases(status: str | None = None) -> list[dict]:
    cases = store().list("ts_cases", order_by="created_at", desc=True)
    return [c for c in cases if not status or c["status"] == status]


def case_detail(case_id: str) -> dict:
    c = store().get("ts_cases", case_id)
    if not c:
        raise HTTPException(404, "case not found")
    return assessment_detail(c["assessment_id"])


def assessment_detail(as_id: str) -> dict:
    s = store()
    a = s.get("ts_assessments", as_id)
    if not a:
        raise HTTPException(404, "assessment not found")
    c = s.get("ts_cases", "case_" + as_id.split("_", 1)[1])
    evs = [s.get("ts_evidence", e) for e in a["evidence_ids"]]
    return {"case": c, "assessment": a,
            "evidence": [{"evidence_id": e["evidence_id"], "kind": e["kind"],
                          "url": f"/api/ts/evidence/{e['evidence_id']}/content" if e["kind"] != "text" else None,
                          "text": redact(e["text"]) if e.get("text") else None} for e in evs if e]}


def resolve_case(case_id: str, verdict: str, notes: str, analyst: str) -> dict:
    s = store()
    c = s.get("ts_cases", case_id)
    if not c:
        raise HTTPException(404, "case not found")
    a = s.get("ts_assessments", c["assessment_id"])
    s.update("ts_cases", case_id, {"status": verdict, "notes": notes, "resolved_by": analyst, "resolved_at": now_iso()})
    s.update("ts_payments", a["payment_id"], {"status": "released" if verdict == "released" else "confirmed_scam"})
    s.update("ts_assessments", a["assessment_id"], {"status": verdict})
    learned = []
    if verdict == "confirmed_scam":
        camp = a["matched_campaigns"][0] if a["matched_campaigns"] else _new_campaign(a)
        all_ind = a["indicators"] + [{"hash": a["beneficiary"]["account_hash"], "kind": "account",
                                      "display": a["beneficiary"]["account_masked"]}]
        for ind in all_ind:
            existing = s.get("ts_indicators", ind["hash"])
            if existing:
                s.update("ts_indicators", ind["hash"], {"reports": existing["reports"] + 1, "last_seen": now_iso(),
                                                        "confidence": max(existing["confidence"], 0.9)})
            else:
                s.set("ts_indicators", ind["hash"], {
                    "hash": ind["hash"], "kind": ind["kind"], "display": ind["display"], "campaign_id": camp,
                    "confidence": 0.9, "reports": 1, "banks_reporting": ["TrustBank"],
                    "first_seen": now_iso(), "last_seen": now_iso()})
                cdoc = s.get("ts_campaigns", camp)
                s.update("ts_campaigns", camp, {"indicator_hashes": cdoc["indicator_hashes"] + [ind["hash"]]})
                learned.append(ind["display"])
        cdoc = s.get("ts_campaigns", camp)
        s.update("ts_campaigns", camp, {"victim_count": cdoc["victim_count"] + 1, "summary": None})
    bus().publish("case.resolved", {"case_id": case_id, "assessment_id": a["assessment_id"], "verdict": verdict,
                                    "amount": a["amount"], "learned_indicators": len(learned)})
    return {"case_id": case_id, "status": verdict, "learned_indicators": learned}


def _new_campaign(a: dict) -> str:
    cid = "C-" + a["assessment_id"][-4:].upper()
    store().set("ts_campaigns", cid, {
        "campaign_id": cid, "label": f"New {(a['analysis'] or {}).get('scam_type', 'scam')} pattern",
        "scam_type": (a["analysis"] or {}).get("scam_type", "other"), "indicator_hashes": [], "victim_count": 0,
        "banks_reporting": ["TrustBank"], "confidence": 0.7, "status": "emerging", "summary": None})
    return cid


# =========================================================================== intel sharing (consortium)
def bank_b_share(req: ShareIndicator) -> dict:
    """Simulates Bank B's node: it hashes locally, and ONLY the hash + metadata crosses the boundary."""
    h = indicator_hash(req.kind, req.value)
    payload = {"kind": req.kind, "hash": h, "campaign_hint": req.campaign_hint,
               "confidence": req.confidence, "from_bank": req.from_bank}
    receipt = ingest_shared(payload)
    return {"transmitted_payload": payload, "receipt": receipt}


def ingest_shared(p: dict) -> dict:
    s = store()
    existing = s.get("ts_indicators", p["hash"])
    if existing:
        banks = sorted(set(existing.get("banks_reporting", [])) | {p["from_bank"]})
        s.update("ts_indicators", p["hash"], {"banks_reporting": banks, "reports": existing["reports"] + 1,
                                              "confidence": round(min(0.99, max(existing["confidence"],
                                                                                 p["confidence"]) + 0.03), 2),
                                              "last_seen": now_iso()})
        status = f"matched existing indicator in {existing['campaign_id']}; confidence raised"
        camp = existing["campaign_id"]
    else:
        camp = p.get("campaign_hint") if p.get("campaign_hint") and s.get("ts_campaigns", p["campaign_hint"]) else None
        if not camp:
            camp = "C-EXT"
            if not s.get("ts_campaigns", camp):
                s.set("ts_campaigns", camp, {"campaign_id": camp, "label": "Externally reported indicators",
                                             "scam_type": "other", "indicator_hashes": [], "victim_count": 0,
                                             "banks_reporting": [p["from_bank"]], "confidence": 0.6,
                                             "status": "emerging", "summary": None})
        s.set("ts_indicators", p["hash"], {
            "hash": p["hash"], "kind": p["kind"], "display": f"{p['kind']} #{p['hash'][:8]} (shared)",
            "campaign_id": camp, "confidence": p["confidence"], "reports": 1, "banks_reporting": [p["from_bank"]],
            "first_seen": now_iso(), "last_seen": now_iso()})
        c = s.get("ts_campaigns", camp)
        s.update("ts_campaigns", camp, {"indicator_hashes": c["indicator_hashes"] + [p["hash"]]})
        status = f"new indicator added to {camp}"
    bus().publish("intel.shared", {"hash": p["hash"], "from_bank": p["from_bank"], "campaign": camp})
    return {"status": status, "campaign_id": camp}


# =========================================================================== graph
def graph_for_assessment(as_id: str) -> dict:
    s = store()
    a = s.get("ts_assessments", as_id)
    if not a:
        raise HTTPException(404, "assessment not found")
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(i, label, typ, **kw):
        nodes.setdefault(i, {"id": i, "label": label, "type": typ, **kw})

    def edge(a_, b_, label=""):
        edges.append({"id": f"{a_}->{b_}", "source": a_, "target": b_, "label": label})

    pid = f"pay:{as_id}"
    node(pid, f"This payment\n{a['amount_fmt']}", "payment", decision=a["final_decision"])
    bh = a["beneficiary"]["account_hash"]
    node(bh, f"Payee {a['beneficiary']['account_masked']}", "account")
    edge(pid, bh, "pays")
    for ind in a["indicators"]:
        node(ind["hash"], ind["display"], ind["kind"])
        edge(pid, ind["hash"], "in evidence")
    camps = set()
    for h in [bh] + [i["hash"] for i in a["indicators"]]:
        hit = s.get("ts_indicators", h)
        if hit:
            nodes[h]["flagged"] = True
            camps.add(hit["campaign_id"])
            edge(h, f"camp:{hit['campaign_id']}", "linked to")
    for c in camps:
        _expand_campaign(c, nodes, edges, node, edge)
    return {"nodes": list(nodes.values()), "edges": edges, "campaigns": sorted(camps)}


def graph_for_campaign(cid: str) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(i, label, typ, **kw):
        nodes.setdefault(i, {"id": i, "label": label, "type": typ, **kw})

    def edge(a_, b_, label=""):
        edges.append({"id": f"{a_}->{b_}", "source": a_, "target": b_, "label": label})

    _expand_campaign(cid, nodes, edges, node, edge)
    return {"nodes": list(nodes.values()), "edges": edges, "campaigns": [cid]}


def _expand_campaign(cid, nodes, edges, node, edge) -> None:
    s = store()
    c = s.get("ts_campaigns", cid)
    if not c:
        return
    node(f"camp:{cid}", f"{cid}\n{c['label']}", "campaign", victims=c["victim_count"])
    for h in c["indicator_hashes"]:
        ind = s.get("ts_indicators", h)
        if not ind:
            continue
        node(h, ind["display"], ind["kind"], flagged=True, banks=ind.get("banks_reporting", []))
        if not any(e["source"] == h and e["target"] == f"camp:{cid}" for e in edges):
            edge(h, f"camp:{cid}", "linked to")
    for v in s.list("ts_victim_links", where={"campaign_id": cid}):
        vid = f"victim:{v['id']}"
        node(vid, f"{fmt_inr(v['amount'])} · {v['bank']}\n{v['days_ago']}d ago", "victim")
        edge(vid, v["indicator_hash"], "paid")


def campaign_summary(cid: str) -> dict:
    s = store()
    c = s.get("ts_campaigns", cid)
    if not c:
        raise HTTPException(404, "campaign not found")
    if c.get("summary"):
        return c["summary"]
    inds = [s.get("ts_indicators", h) for h in c["indicator_hashes"]]
    recent = [a for a in s.list("ts_assessments", order_by="created_at", desc=True, limit=100)
              if cid in a.get("matched_campaigns", [])][:20]
    facts = {
        "campaign_id": cid, "label": c["label"], "scam_type": c["scam_type"], "victims": c["victim_count"],
        "banks_reporting": c["banks_reporting"],
        "indicators": [{"kind": i["kind"], "display": i["display"], "reports": i["reports"]} for i in inds if i],
        "recent_evidence_summaries": [(a["analysis"] or {}).get("summary") for a in recent if a.get("analysis")],
        "recent_amounts": [a["amount"] for a in recent],
    }
    summary = None
    if gemini().live:
        try:
            summary = gemini().structured(
                "Summarise this scam campaign for a bank fraud analyst. Use only these facts:\n"
                + json.dumps(facts, ensure_ascii=False), CampaignSummary, model=settings.deep_model,
                purpose="campaign_summary").model_dump()
            summary["generated_by"] = f"gemini:{settings.deep_model}"
        except GeminiUnavailable:
            summary = None
    if summary is None:
        kinds = sorted({i["kind"] for i in inds if i})
        summary = {
            "title": f"{cid}: {c['label']}",
            "narrative": f"Active {c['scam_type'].replace('_', ' ')} campaign with {c['victim_count']} synthetic "
                         f"victims across {len(c['banks_reporting'])} bank(s), using {len(inds)} indicators "
                         f"({', '.join(kinds)}).",
            "modus_operandi": ["Unsolicited message creates urgency or a reward",
                               "Victim is pushed to pay a newly added payee",
                               "Funds move through mule accounts shared across victims"],
            "recommended_actions": ["Block listed mule accounts", "Takedown request for phishing domains",
                                    "Proactive SMS warning to customers who received similar messages"],
            "generated_by": "template",
        }
    s.update("ts_campaigns", cid, {"summary": summary})
    return summary


# =========================================================================== insights
def insights() -> dict:
    s = store()
    items = s.list("ts_assessments")
    by = {"PASS": 0, "WARN": 0, "HOLD": 0}
    protected = 0.0
    lat = []
    for a in items:
        by[a["final_decision"]] += 1
        lat.append(a["latency_ms"]["total"])
        if a["final_decision"] == "HOLD" or a.get("payment_status") == "cancelled":
            protected += a["amount"]
    lat.sort()
    return {
        "assessments": len(items), "decisions": by, "value_protected": protected,
        "value_protected_fmt": fmt_inr(protected),
        "latency_p50": lat[len(lat) // 2] if lat else None,
        "latency_p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
        "open_cases": len([c for c in s.list("ts_cases") if c["status"] == "open"]),
        "campaigns": len(s.list("ts_campaigns")), "indicators": s.count("ts_indicators"),
        "events": bus().recent(20, prefix="")[:20],
    }
