from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from ..core.auth import current_user
from ..core.blobs import blobs
from ..core.store import store
from . import data, evaluation, service
from .samples import SAMPLES, sample_png
from .schemas import (AssessRequest, NewBeneficiary, PaymentAction, ResolveCase, SafetyAnswers, ShareIndicator)

router = APIRouter(prefix="/api/ts", tags=["trustshield"])
MAX_UPLOAD = 8 * 1024 * 1024


@router.get("/customers")
def customers(user=Depends(current_user)):
    s = store()
    out = []
    for c in s.list("ts_customers"):
        bens = [b for b in s.list("ts_beneficiaries", where={"customer_id": c["customer_id"]})]
        bens.sort(key=lambda b: b["added_at"], reverse=True)
        out.append({**c, "beneficiaries": bens})
    return {"customers": out, "suggested_payees": data.SUGGESTED_PAYEES}


@router.post("/beneficiaries")
def add_beneficiary(req: NewBeneficiary, user=Depends(current_user)):
    return service.add_beneficiary(req)


@router.get("/samples")
def samples():
    return [{"id": s.id, "title": s.title, "channel": s.channel, "label": s.label,
             "image_url": f"/api/ts/samples/{s.id}.png"} for s in SAMPLES]


@router.get("/samples/{sample_id}.png")
def sample_image(sample_id: str):
    try:
        return Response(sample_png(sample_id), media_type="image/png", headers={"Cache-Control": "max-age=3600"})
    except KeyError:
        raise HTTPException(404, "unknown sample") from None


@router.post("/evidence/sample")
def evidence_sample(customer_id: str = Form(...), sample_id: str = Form(...), user=Depends(current_user)):
    return service.save_evidence(customer_id, "sample", sample_id=sample_id, mime="image/png")


@router.post("/evidence/text")
def evidence_text(customer_id: str = Form(...), text: str = Form(...), user=Depends(current_user)):
    return service.save_evidence(customer_id, "text", text=text[:5000])


@router.post("/evidence/upload")
async def evidence_upload(customer_id: str = Form(...), file: UploadFile = File(...), user=Depends(current_user)):
    if file.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(415, "png, jpeg or webp only")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "file too large")
    ev = service.save_evidence(customer_id, "image", mime=file.content_type)
    key = f"evidence/{customer_id}/{ev['evidence_id']}"
    blobs().put(key, raw, file.content_type)
    store().update("ts_evidence", ev["evidence_id"], {"blob_key": key})
    return {**ev, "blob_key": key}


@router.get("/evidence/{ev_id}/content")
def evidence_content(ev_id: str, user=Depends(current_user)):
    ev = store().get("ts_evidence", ev_id)
    if not ev:
        raise HTTPException(404)
    if ev["kind"] == "sample":
        return Response(sample_png(ev["sample_id"]), media_type="image/png")
    if ev["kind"] == "image":
        data_, mime = blobs().get(ev["blob_key"])
        return Response(data_, media_type=mime)
    raise HTTPException(404, "text evidence has no binary content")


@router.post("/assess")
def assess(req: AssessRequest, user=Depends(current_user)):
    return service.assess(req)


@router.get("/assessments/{as_id}")
def get_assessment(as_id: str, user=Depends(current_user)):
    a = store().get("ts_assessments", as_id)
    if not a:
        raise HTTPException(404)
    return a


@router.get("/assessments/{as_id}/detail")
def assessment_detail(as_id: str, user=Depends(current_user)):
    return service.assessment_detail(as_id)


@router.get("/assessments")
def list_assessments(limit: int = 30, user=Depends(current_user)):
    return store().list("ts_assessments", order_by="created_at", desc=True, limit=limit)


@router.post("/assessments/{as_id}/answers")
def answers(as_id: str, req: SafetyAnswers, user=Depends(current_user)):
    return service.submit_answers(as_id, req.answers)


@router.post("/payments/{pay_id}/action")
def payment_action(pay_id: str, req: PaymentAction, user=Depends(current_user)):
    return service.payment_action(pay_id, req.action)


@router.get("/cases")
def cases(status: str | None = None, user=Depends(current_user)):
    return service.list_cases(status)


@router.get("/cases/{case_id}")
def case(case_id: str, user=Depends(current_user)):
    return service.case_detail(case_id)


@router.post("/cases/{case_id}/resolve")
def resolve(case_id: str, req: ResolveCase, user=Depends(current_user)):
    return service.resolve_case(case_id, req.verdict, req.notes, user["uid"])


@router.get("/graph/assessment/{as_id}")
def graph_assessment(as_id: str, user=Depends(current_user)):
    return service.graph_for_assessment(as_id)


@router.get("/graph/campaign/{cid}")
def graph_campaign(cid: str, user=Depends(current_user)):
    return service.graph_for_campaign(cid)


@router.get("/campaigns")
def campaigns(user=Depends(current_user)):
    return store().list("ts_campaigns", order_by="campaign_id")


@router.get("/campaigns/{cid}/summary")
def campaign_summary(cid: str, user=Depends(current_user)):
    return service.campaign_summary(cid)


@router.get("/indicators")
def indicators(user=Depends(current_user)):
    return store().list("ts_indicators", order_by="last_seen", desc=True)


@router.post("/intel/bank-b/share")
def share(req: ShareIndicator, user=Depends(current_user)):
    return service.bank_b_share(req)


@router.get("/insights")
def insights(user=Depends(current_user)):
    return service.insights()


@router.post("/eval/run")
def eval_run(n: int = 400, live: bool = True, user=Depends(current_user)):
    return evaluation.run(n=min(max(n, 40), 1000), live=live)


@router.get("/eval/latest")
def eval_latest(user=Depends(current_user)):
    return evaluation.latest()


@router.post("/demo/reset")
def reset(user=Depends(current_user)):
    return data.seed(force=True)
