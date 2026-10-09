"""Stage 5 - customer intervention + analyst rationale.

Gemini only verbalises the signals it is given; output is validated (signal_codes_used must be a subset of
the input codes) and falls back to deterministic templates (EN/HI) if validation or the call fails."""
from __future__ import annotations

import json
import logging

from ..config import settings
from ..core.gemini import GeminiUnavailable, gemini
from ..core.util import fmt_inr
from .schemas import Intervention, SafetyQuestion, ScamAnalysis, Signal

log = logging.getLogger("explain")
PROMPT_VERSION = "intervention_v1"

SYSTEM = """You write fraud-prevention interventions for TrustBank customers who are about to send money.
- Use ONLY the signals provided. Do not invent new reasons. List the codes you used in signal_codes_used.
- customer_message: max 80 words, warm, plain language (reading age ~12), never blame the customer,
  never say the customer is stupid; say what to do next. Write it in the customer's language.
- why_points: 2-4 short bullets, each grounded in one provided signal.
- safety_questions: 2-3 yes/no questions tailored to the suspected scam pattern that would reveal coercion.
  escalate_if = the answer that indicates a scam. ids q1, q2, q3.
- analyst_rationale: 2-3 sentences, factual, English, cite the strongest signals.
- Decision semantics: WARN = customer may continue after the check; HOLD = payment paused, bank will call back."""

LANG_NAME = {"en": "English", "hi": "Hindi (Devanagari script)", "ta": "Tamil"}

# ------------------------------------------------------------------ templates
HEADLINES = {
    "en": {"PASS": "Payment looks normal", "WARN": "Please pause – this may be a scam",
           "HOLD": "We've paused this payment to protect you"},
    "hi": {"PASS": "भुगतान सामान्य है",
           "WARN": "रुकिए – यह धोखा हो सकता है",
           "HOLD": "आपकी सुरक्षा के लिए हमने यह भुगतान रोक दिया है"},
}
MESSAGES = {
    "en": {
        "WARN": "Something about this payment matches patterns we see in scams. Banks and officials will never ask "
                "you to move money to verify your account. Please answer a few quick questions before you decide.",
        "HOLD": "This payment of {amount} shows strong signs of a scam, so we have paused it. Your money is safe. "
                "Please do not reply to the message. Call TrustBank on the number printed on your card – "
                "we will also call you shortly.",
    },
    "hi": {
        "WARN": "यह भुगतान धोखाधड़ी जैसा दिख रहा है। "
                "बैंक कभी भी खाता सत्यापन के लिए पैसे भेजने को नहीं कहता। "
                "कृपया कुछ सवालों का जवाब दें।",
        "HOLD": "{amount} का यह भुगतान धोखा लग रहा है, इसलिए हमने इसे रोक दिया है। "
                "आपका पैसा सुरक्षित है। संदेश का जवाब न दें। "
                "कार्ड पर छपे नंबर पर TrustBank को कॉल करें।",
    },
}
QUESTIONS = {
    "bank_impersonation": [
        ("Did someone claiming to be from the bank ask you to make this payment?", "yes"),
        ("Were you told your account will be blocked unless you pay or verify?", "yes"),
        ("Has anyone asked you to keep this payment secret or install an app?", "yes"),
    ],
    "investment": [
        ("Were you promised guaranteed or very high returns?", "yes"),
        ("Did you meet this investment contact only online or on a messaging app?", "yes"),
    ],
    "job_task": [
        ("Is this payment to 'unlock' tasks or earnings from an online job?", "yes"),
        ("Have you been paid small amounts first and now asked to deposit more?", "yes"),
    ],
    "parcel_delivery": [
        ("Did you get this payment request from an SMS link about a parcel?", "yes"),
        ("Are you expecting a delivery from this company?", "no"),
    ],
    "default": [
        ("Is someone telling you to make this payment right now?", "yes"),
        ("Have you met or spoken to the person you are paying in real life?", "no"),
        ("Has anyone asked you to keep this payment secret?", "yes"),
    ],
}
QUESTIONS_HI = {
    "Did someone claiming to be from the bank ask you to make this payment?":
        "क्या किसी ने बैंक से होने का दावा करके यह भुगतान करने को कहा?",
    "Were you told your account will be blocked unless you pay or verify?":
        "क्या आपसे कहा गया कि भुगतान नहीं किया तो खाता बंद हो जाएगा?",
    "Has anyone asked you to keep this payment secret or install an app?":
        "क्या किसी ने इसे गुप्त रखने या कोई ऐप इंस्टॉल करने को कहा?",
}


def template_intervention(decision: str, signals: list[Signal], a: ScamAnalysis | None, lang: str,
                          amount: float) -> Intervention:
    lang = lang if lang in HEADLINES else "en"
    top = [s for s in signals if s.contribution > 0][:4] or signals[:3]
    if decision == "PASS":
        return Intervention(headline=HEADLINES[lang]["PASS"], customer_message="", why_points=[],
                            signal_codes_used=[], safety_questions=[],
                            analyst_rationale="No material risk signals.")
    stype = a.scam_type if a and a.scam_type in QUESTIONS else "default"
    qs = QUESTIONS[stype]
    questions = [SafetyQuestion(id=f"q{i + 1}", text=QUESTIONS_HI.get(t, t) if lang == "hi" else t, escalate_if=e)
                 for i, (t, e) in enumerate(qs[:3])]
    return Intervention(
        headline=HEADLINES[lang][decision],
        customer_message=MESSAGES[lang][decision].format(amount=fmt_inr(amount)),
        why_points=[s.text for s in top],
        signal_codes_used=[s.code for s in top],
        safety_questions=questions if decision == "WARN" else questions[:2],
        analyst_rationale="; ".join(f"{s.code} ({s.contribution:+.2f})" for s in top),
    )


def generate(decision: str, signals: list[Signal], a: ScamAnalysis | None, profile: dict,
             amount: float) -> tuple[Intervention, dict]:
    lang = profile.get("language", "en")
    if decision == "PASS" or not gemini().live:
        return template_intervention(decision, signals, a, lang, amount), {"explainer": "template"}
    allowed = {s.code for s in signals}
    payload = {
        "decision": decision, "amount": fmt_inr(amount), "customer_language": LANG_NAME.get(lang, "English"),
        "customer_age_band": profile.get("age_band"),
        "signals": [{"code": s.code, "text": s.text, "contribution": s.contribution} for s in signals[:8]],
        "scam_type": a.scam_type if a else "unknown", "evidence_summary": a.summary if a else None,
    }
    prompt = "Write the intervention for this assessment:\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    for attempt in range(2):
        try:
            iv = gemini().structured(prompt, Intervention, system=SYSTEM, temperature=0.3, purpose="intervention")
        except GeminiUnavailable as e:
            log.warning("intervention generation failed: %s", e)
            break
        bad = set(iv.signal_codes_used) - allowed
        if not bad and iv.signal_codes_used:
            return iv, {"explainer": f"gemini:{settings.fast_model}", "faithful": True, "attempts": attempt + 1}
        prompt += f"\nYour previous answer used codes not in the input: {sorted(bad)}. Use only provided codes."
    return template_intervention(decision, signals, a, lang, amount), {"explainer": "template-fallback",
                                                                       "faithful": True}
