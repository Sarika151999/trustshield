"""Pydantic models: Gemini response schemas + API contracts."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TacticName = Literal[
    "urgency", "authority_impersonation", "threat_or_fear", "secrecy_request", "fake_verification_otp",
    "suspicious_link", "too_good_to_be_true", "romance_or_trust_building", "remote_access_request",
    "safe_account_transfer", "payment_redirect_change_of_details", "emotional_pressure",
]
ScamType = Literal[
    "bank_impersonation", "government_impersonation", "investment", "job_task", "romance", "parcel_delivery",
    "tech_support", "invoice_redirect", "family_emergency", "none", "other",
]
Decision = Literal["PASS", "WARN", "HOLD"]


# ---------------------------------------------------------------- Gemini output schemas
# (no default values: keeps the JSON schema sent to Gemini simple)
class Tactic(BaseModel):
    name: TacticName
    evidence_quote: str = Field(description="Exact short span copied verbatim from the evidence")
    severity: float = Field(description="0..1 how strongly this tactic indicates manipulation")


class Entities(BaseModel):
    urls: list[str]
    phone_numbers: list[str]
    account_numbers: list[str]
    upi_ids: list[str]
    impersonated_org: str | None
    sender_id: str | None


class ScamAnalysis(BaseModel):
    transcript: str = Field(description="Verbatim text content of all evidence (OCR for images)")
    is_scam_likely: bool
    scam_type: ScamType
    confidence: float = Field(description="0..1 confidence in is_scam_likely")
    legitimate_context_confidence: float = Field(
        description="0..1 how strongly the evidence supports a genuine, non-coerced purpose for this payment")
    tactics: list[Tactic]
    entities: Entities
    payment_link: Literal["explicitly_requests_this_payment", "related", "unrelated", "unknown"]
    language: str
    summary: str = Field(description="One neutral sentence describing the evidence")


class SafetyQuestion(BaseModel):
    id: str
    text: str
    escalate_if: Literal["yes", "no"]


class Intervention(BaseModel):
    headline: str
    customer_message: str
    why_points: list[str]
    signal_codes_used: list[str]
    safety_questions: list[SafetyQuestion]
    analyst_rationale: str


class CampaignSummary(BaseModel):
    title: str
    narrative: str
    modus_operandi: list[str]
    recommended_actions: list[str]


# ---------------------------------------------------------------- API contracts
class PaymentContext(BaseModel):
    active_call: bool = False
    new_device: bool = False
    hour: int | None = None


class AssessRequest(BaseModel):
    customer_id: str
    ben_id: str
    amount: float = Field(gt=0)
    currency: str = "INR"
    note: str = ""
    channel: str = "mobile"
    context: PaymentContext = PaymentContext()
    evidence_ids: list[str] = []


class NewBeneficiary(BaseModel):
    customer_id: str
    display_name: str
    account: str
    bank_code: str = "PAYB"
    type: Literal["bank_account", "upi", "wallet"] = "bank_account"


class SafetyAnswers(BaseModel):
    answers: dict[str, Literal["yes", "no"]]


class PaymentAction(BaseModel):
    action: Literal["confirm", "cancel"]


class ResolveCase(BaseModel):
    verdict: Literal["released", "confirmed_scam"]
    notes: str = ""


class ShareIndicator(BaseModel):
    kind: Literal["phone", "url_domain", "account", "upi"]
    value: str
    campaign_hint: str | None = None
    confidence: float = 0.8
    from_bank: str = "Bank B"


class Signal(BaseModel):
    code: str
    component: Literal["behaviour", "content", "intel", "legit"]
    strength: float
    text: str
    contribution: float = 0.0
