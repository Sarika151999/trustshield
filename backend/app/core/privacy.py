"""Indicator normalisation + HMAC hashing, and PII redaction (regex, or Cloud DLP when enabled)."""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
from urllib.parse import urlparse

from ..config import settings

log = logging.getLogger("privacy")


def normalise(kind: str, value: str) -> str:
    v = value.strip().lower()
    if kind == "phone":
        digits = re.sub(r"\D", "", v)
        if len(digits) == 10:
            digits = "91" + digits
        return "+" + digits
    if kind == "url_domain":
        if "://" not in v:
            v = "http://" + v
        host = urlparse(v).hostname or v
        return host.removeprefix("www.")
    if kind == "account":
        return re.sub(r"\D", "", v)
    if kind == "upi":
        return v.replace(" ", "")
    return v


def indicator_hash(kind: str, value: str) -> str:
    norm = normalise(kind, value)
    return hmac.new(settings.hmac_salt.encode(), f"{kind}:{norm}".encode(), hashlib.sha256).hexdigest()[:32]


def mask(kind: str, value: str) -> str:
    n = normalise(kind, value)
    if kind == "phone":
        return n[:5] + "•••" + n[-3:]
    if kind == "account":
        return "••••" + n[-4:]
    if kind == "url_domain":
        parts = n.split(".")
        head = parts[0]
        return (head[:6] + "•••" if len(head) > 6 else head) + "." + ".".join(parts[1:])
    if kind == "upi":
        user, _, bank = n.partition("@")
        return user[:3] + "•••@" + bank
    return n


_PATTERNS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN]"),
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "[CARD]"),
    (re.compile(r"\b\d{9,18}\b"), "[ACCOUNT]"),
    (re.compile(r"(?<!\w)(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}\b"), "[PHONE]"),
    (re.compile(r"\b\d{4,8}\b(?=\D{0,20}\b(?:otp|OTP|code)\b)"), "[OTP]"),
]


def redact(text: str) -> str:
    if not text:
        return text
    if settings.dlp_enabled:
        try:
            return _dlp_redact(text)
        except Exception as e:  # noqa: BLE001
            log.warning("DLP failed, using regex redaction: %s", e)
    out = text
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    return out


def _dlp_redact(text: str) -> str:
    from google.cloud import dlp_v2

    client = dlp_v2.DlpServiceClient()
    info_types = [{"name": n} for n in ("PERSON_NAME", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD_NUMBER",
                                        "IBAN_CODE", "INDIA_PAN_INDIVIDUAL", "INDIA_AADHAAR_INDIVIDUAL")]
    resp = client.deidentify_content(request={
        "parent": f"projects/{settings.project}/locations/global",
        "inspect_config": {"info_types": info_types},
        "deidentify_config": {"info_type_transformations": {"transformations": [
            {"primitive_transformation": {"replace_with_info_type_config": {}}}]}},
        "item": {"value": text},
    })
    return resp.item.value
