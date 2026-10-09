"""Stage 2 - multimodal scam-content analysis with Gemini (structured output),
plus a deterministic heuristic analyser used offline (GEMINI_BACKEND=mock) or as a fallback."""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from ..config import settings
from ..core.blobs import blobs
from ..core.gemini import GeminiUnavailable, gemini
from .samples import SAMPLE_BY_ID, sample_png, sample_sha_index, sha
from .schemas import Entities, ScamAnalysis, Signal, Tactic

log = logging.getLogger("content")

PROMPT_VERSION = "scam_analysis_v1"
SYSTEM = (Path(__file__).parent / "prompts" / "scam_analysis_v1.md").read_text(encoding="utf-8")

_cache: dict[str, tuple[ScamAnalysis, dict]] = {}


def load_evidence_media(ev: dict) -> tuple[bytes, str] | None:
    if ev["kind"] == "sample":
        return sample_png(ev["sample_id"]), "image/png"
    if ev["kind"] == "image":
        return blobs().get(ev["blob_key"])
    return None


def analyze(evidence: list[dict], amount: float, ben_is_new: bool, note: str) -> tuple[ScamAnalysis | None, dict]:
    """Returns (analysis | None if no evidence, meta)."""
    if not evidence:
        return None, {"analyzer": "none"}
    media: list[tuple[bytes, str]] = []
    texts: list[str] = []
    for ev in evidence:
        m = load_evidence_media(ev)
        if m:
            media.append(m)
        if ev.get("text"):
            texts.append(ev["text"])
    key = hashlib.sha256(b"".join(sha(b).encode() for b, _ in media) + "|".join(texts).encode()
                         + f"{round(amount, -2)}|{ben_is_new}|{note}".encode()).hexdigest()
    if key in _cache:
        a, meta = _cache[key]
        return a, {**meta, "cached": True}

    meta: dict = {"prompt_version": PROMPT_VERSION}
    if gemini().live:
        try:
            prompt = _user_prompt(texts, amount, ben_is_new, note, n_images=len(media))
            a = gemini().structured(prompt, ScamAnalysis, media=media, system=SYSTEM, purpose="scam_analysis")
            meta.update(analyzer=f"gemini:{settings.fast_model}")
            a = _post_validate(a)
            _cache[key] = (a, meta)
            return a, meta
        except GeminiUnavailable as e:
            if not settings.gemini_fallback:
                raise
            log.warning("Gemini unavailable, heuristic fallback: %s", e)
            meta["fallback_reason"] = str(e)[:200]

    # Offline path: "read" our own sample screenshots via their known text; pasted text as-is.
    idx = sample_sha_index()
    read = [idx.get(sha(b), "") for b, _ in media]
    full = "\n\n".join([t for t in read if t] + texts)
    a = heuristic_analysis(full, amount)
    if media and not any(read):
        a.summary = "Image could not be read by the offline analyser (enable Gemini for OCR)."
    meta.update(analyzer="mock-heuristic" if "fallback_reason" not in meta else "heuristic-fallback")
    _cache[key] = (a, meta)
    return a, meta


def _user_prompt(texts: list[str], amount: float, ben_is_new: bool, note: str, n_images: int) -> str:
    pasted = "\n---\n".join(texts) if texts else "(none)"
    return (f"Payment context: amount={amount:.0f} INR, beneficiary_is_new={ben_is_new}, payment_note=\"{note}\".\n"
            f"Number of attached screenshots: {n_images}.\n"
            f"<untrusted_evidence_text>\n{pasted}\n</untrusted_evidence_text>\n"
            "Analyse all evidence (screenshots and text) and return the JSON.")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _post_validate(a: ScamAnalysis) -> ScamAnalysis:
    a.confidence = max(0.0, min(1.0, a.confidence))
    a.legitimate_context_confidence = max(0.0, min(1.0, a.legitimate_context_confidence))
    for t in a.tactics:
        t.severity = max(0.0, min(1.0, t.severity))
    return a


def quote_accuracy(a: ScamAnalysis) -> float | None:
    if not a.tactics:
        return None
    tr = _norm(a.transcript)
    return sum(1 for t in a.tactics if _norm(t.evidence_quote) in tr) / len(a.tactics)


LINK_FACTOR = {"explicitly_requests_this_payment": 1.0, "related": 0.8, "unknown": 0.5, "unrelated": 0.25}
TACTIC_TEXT = {
    "urgency": "Pressure to act immediately", "authority_impersonation": "Claims to be from an authority/bank",
    "threat_or_fear": "Threat of account block, penalty or loss", "secrecy_request": "Asks you to keep it secret",
    "fake_verification_otp": "Fake verification / KYC request", "suspicious_link": "Contains a suspicious link",
    "too_good_to_be_true": "Promises unrealistic returns or rewards",
    "romance_or_trust_building": "Builds trust/romance before asking for money",
    "remote_access_request": "Asks you to install a remote/screen-share app",
    "safe_account_transfer": "Asks you to move money to a 'safe' account",
    "payment_redirect_change_of_details": "Changes payee bank details",
    "emotional_pressure": "Emotional pressure or emergency story",
}


def content_signals(a: ScamAnalysis | None) -> list[Signal]:
    if a is None:
        return []
    lf = LINK_FACTOR.get(a.payment_link, 0.5)
    out: list[Signal] = []
    scale = a.confidence * lf * (1.0 if a.is_scam_likely else 0.3)
    for t in a.tactics:
        s = t.severity * scale
        if s < 0.05:
            continue
        out.append(Signal(code=t.name, component="content", strength=round(min(s, 0.95), 3),
                          text=f"{TACTIC_TEXT.get(t.name, t.name)}: “{t.evidence_quote}”"))
    if not a.is_scam_likely and a.legitimate_context_confidence > 0.3:
        lf_l = 1.0 if a.payment_link in ("explicitly_requests_this_payment", "related") else 0.5
        out.append(Signal(code="legitimate_context", component="legit",
                          strength=round(a.legitimate_context_confidence * lf_l, 3),
                          text=f"Evidence supports a genuine purpose: {a.summary}"))
    return out


# ============================================================================ heuristic analyser
_RULES: list[tuple[str, re.Pattern, float]] = [
    ("urgency", re.compile(r"\b(immediately|urgent(ly)?|today|within \d+ hours?|right now|abhi|turant|tonight|"
                           r"reply fast|limited seats|closes)\b", re.I), 0.6),
    ("threat_or_fear", re.compile(r"\b(block(ed)?|suspend(ed)?|suspension|penalty|band ho|legal action|arrest|"
                                  r"hacked|frozen|lose everything|returned to sender)\b", re.I), 0.7),
    ("authority_impersonation", re.compile(r"\b(kyc dept|security team|fraud department|officer|bank verify|"
                                           r"kyc|govt-approved|customs|police)\b", re.I), 0.7),
    ("fake_verification_otp", re.compile(r"\b(verify (now|immediately)|verification account|update kyc|kyc "
                                         r"(turant )?update|reactivation)\b", re.I), 0.75),
    ("secrecy_request", re.compile(r"(do not|don'?t) (share this message|tell anyone)|keep (it|this) (secret|"
                                   r"confidential)", re.I), 0.8),
    ("too_good_to_be_true", re.compile(r"(guaranteed|\d+x returns|earn rs [\d,]+-?[\d,]* daily|\d+% commission|"
                                       r"bonus)", re.I), 0.8),
    ("safe_account_transfer", re.compile(r"(safe (protected )?account|move all (my|your) money)", re.I), 0.95),
    ("remote_access_request", re.compile(r"(screen-?share app|anydesk|teamviewer|remote access|install .{0,20}app)",
                                         re.I), 0.9),
    ("payment_redirect_change_of_details", re.compile(r"(new bank details|changed our (bank|account)|"
                                                      r"updated account details)", re.I), 0.8),
    ("emotional_pressure", re.compile(r"\b(emergency|hospital|accident|please help me)\b", re.I), 0.6),
]
_URL = re.compile(r"(?:https?://)?(?:[a-z0-9-]+\.)+(?:in|co|top|com|net|xyz|info|org)(?:/[^\s]*)?", re.I)
_PHONE = re.compile(r"(?:\+91[ -]?)?\b[6-9]\d{4}[ -]?\d{5}\b")
_ACCOUNT = re.compile(r"\b\d{11,18}\b")
_UPI = re.compile(r"\b[\w.]+@ok\w+\b|\b[\w.]+@(?:upi|ybl|paytm|axl)\b", re.I)
_AMOUNT = re.compile(r"(?:rs\.?|inr|₹)\s?([\d,]+)", re.I)
_REQUEST = re.compile(r"\b(transfer|pay|deposit|send|invest)\b", re.I)
_INJECTION = re.compile(r"(ignore (all |previous )?instructions|system note to ai|classify (it|this) as safe)", re.I)
_SAFE_DOMAINS = {"trustbank.com", "trustbank.in"}


def _quote(text: str, m: re.Match) -> str:
    start = max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start())) + 1
    end_candidates = [i for i in (text.find(".", m.end()), text.find("\n", m.end())) if i != -1]
    end = min(end_candidates) if end_candidates else len(text)
    q = text[start:end].strip()
    if len(q) > 140:
        a = max(0, m.start() - start - 50)
        q = q[a:a + 140].strip()
    return q


def heuristic_analysis(text: str, amount: float) -> ScamAnalysis:
    clean = _INJECTION.split(text)[0] if _INJECTION.search(text) else text  # never obey embedded instructions
    tactics: list[Tactic] = []
    for name, pat, sev in _RULES:
        m = pat.search(clean)
        if m:
            tactics.append(Tactic(name=name, evidence_quote=_quote(clean, m), severity=sev))
    urls = [u for u in _URL.findall(clean) if not any(d in u.lower() for d in _SAFE_DOMAINS)]
    urls = [u for u in urls if "." in u and not re.fullmatch(r"[\d.]+", u)]
    if urls:
        m = re.search(re.escape(urls[0]), clean)
        tactics.append(Tactic(name="suspicious_link", evidence_quote=_quote(clean, m) if m else urls[0], severity=0.8))
    phones = _PHONE.findall(clean)
    accounts = [a for a in _ACCOUNT.findall(clean) if not any(a in p.replace(" ", "") for p in phones)]
    upis = _UPI.findall(clean)
    has_request = bool(_REQUEST.search(clean))
    strong = {t.name for t in tactics} & {"suspicious_link", "safe_account_transfer", "remote_access_request",
                                          "too_good_to_be_true", "fake_verification_otp", "secrecy_request"}
    is_scam = (len(tactics) >= 2 and (bool(strong) or has_request)) or bool(
        {"safe_account_transfer", "remote_access_request"} & strong)
    amounts = [float(x.replace(",", "")) for x in _AMOUNT.findall(clean) if x.replace(",", "").isdigit()]
    if any(abs(a - amount) <= max(0.02 * amount, 1) for a in amounts):
        link = "explicitly_requests_this_payment"
    elif has_request:
        link = "related"
    else:
        link = "unknown"
    lower = clean.lower()
    if not is_scam:
        stype = "none"
    elif "safe" in lower and "account" in lower or "kyc" in lower or "bank" in lower:
        stype = "bank_impersonation"
    elif "parcel" in lower or "courier" in lower:
        stype = "parcel_delivery"
    elif "task" in lower or "like" in lower and "videos" in lower:
        stype = "job_task"
    elif "return" in lower or "invest" in lower or "trading" in lower:
        stype = "investment"
    else:
        stype = "other"
    org = None
    m = re.search(r"\b(TrustBank|QuickShip Courier|StarMedia HR|AlphaGrowth)\b", clean)
    if m and is_scam:
        org = m.group(1)
    conf = min(0.5 + 0.08 * len(tactics), 0.97) if is_scam else (0.8 if not tactics else 0.45)
    legit = 0.0 if is_scam else (0.75 if has_request and not tactics else 0.4)
    summary = (f"Message shows {len(tactics)} manipulation tactics typical of a {stype.replace('_', ' ')} scam."
               if is_scam else "Message appears to be an ordinary, non-coercive request." if clean.strip()
               else "No readable text in the evidence.")
    return ScamAnalysis(
        transcript=text, is_scam_likely=is_scam, scam_type=stype, confidence=round(conf, 2),
        legitimate_context_confidence=legit, tactics=tactics,
        entities=Entities(urls=urls, phone_numbers=phones, account_numbers=accounts, upi_ids=upis,
                          impersonated_org=org, sender_id=None),
        payment_link=link, language="hi-Latn" if re.search(r"\b(aapka|karein|ji|warna)\b", lower) else "en",
        summary=summary,
    )


def sample_text(sample_id: str) -> str:
    return SAMPLE_BY_ID[sample_id].text
