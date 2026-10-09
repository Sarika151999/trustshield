"""Stage 3 - indicator intelligence: hashed-indicator watchlist lookups (+ optional Web Risk)."""
from __future__ import annotations

import logging

from ..config import settings
from ..core.privacy import indicator_hash, mask
from ..core.store import store
from .schemas import ScamAnalysis, Signal

log = logging.getLogger("intel")
KIND_TEXT = {"url_domain": "Link domain", "phone": "Phone number", "account": "Account", "upi": "UPI ID"}


def extract_indicators(a: ScamAnalysis | None) -> list[tuple[str, str]]:
    if a is None:
        return []
    e = a.entities
    out = [("url_domain", u) for u in e.urls] + [("phone", p) for p in e.phone_numbers]
    out += [("account", x) for x in e.account_numbers] + [("upi", u) for u in e.upi_ids]
    seen, uniq = set(), []
    for kind, v in out:
        h = indicator_hash(kind, v)
        if h not in seen:
            seen.add(h)
            uniq.append((kind, v))
    return uniq


def lookup(a: ScamAnalysis | None, ben: dict) -> tuple[list[Signal], list[dict], list[str]]:
    """Returns (signals, matches, all_indicator_hashes)."""
    s = store()
    signals: list[Signal] = []
    matches: list[dict] = []
    hashes: list[str] = []

    # 1) the beneficiary account itself
    ben_hit = s.get("ts_indicators", ben["account_hash"]) if ben.get("account_hash") else None
    hashes.append(ben.get("account_hash", ""))
    if ben_hit:
        camp = s.get("ts_campaigns", ben_hit["campaign_id"]) or {}
        signals.append(Signal(code="beneficiary_known_mule", component="intel", strength=ben_hit["confidence"],
                              text=f"Payee account {ben_hit['display']} is a reported mule account in campaign "
                                   f"{ben_hit['campaign_id']} ({camp.get('victim_count', '?')} victims)"))
        matches.append({**ben_hit, "source": "beneficiary"})

    # 2) indicators extracted from the evidence
    for kind, value in extract_indicators(a):
        h = indicator_hash(kind, value)
        hashes.append(h)
        if h == ben.get("account_hash"):
            continue
        hit = s.get("ts_indicators", h)
        if hit:
            camp = s.get("ts_campaigns", hit["campaign_id"]) or {}
            banks = len(hit.get("banks_reporting", []))
            signals.append(Signal(code="indicator_match", component="intel", strength=round(hit["confidence"] * 0.9, 3),
                                  text=f"{KIND_TEXT[kind]} {mask(kind, value)} is linked to active campaign "
                                       f"{hit['campaign_id']} – {camp.get('label', '')} (reported by {banks} "
                                       f"bank{'s' if banks != 1 else ''})"))
            matches.append({**hit, "source": "evidence"})
        elif kind == "url_domain" and settings.webrisk_enabled:
            threat = _webrisk(value)
            if threat:
                signals.append(Signal(code="webrisk_threat", component="intel", strength=0.85,
                                      text=f"Google Web Risk flags {mask(kind, value)} as {threat}"))

    camps = {m["campaign_id"] for m in matches}
    for c in camps:
        n = sum(1 for m in matches if m["campaign_id"] == c)
        if n >= 2:
            signals.append(Signal(code="campaign_corroboration", component="intel", strength=0.3,
                                  text=f"{n} independent indicators point to the same campaign {c}"))
    return signals, matches, [h for h in hashes if h]


def _webrisk(url: str) -> str | None:
    try:
        from google.cloud import webrisk_v1

        client = webrisk_v1.WebRiskServiceClient()
        resp = client.search_uris(uri=url if "://" in url else f"http://{url}",
                                  threat_types=[webrisk_v1.ThreatType.SOCIAL_ENGINEERING, webrisk_v1.ThreatType.MALWARE])
        if resp.threat and resp.threat.threat_types:
            return ", ".join(t.name for t in resp.threat.threat_types)
    except Exception as e:  # noqa: BLE001
        log.warning("web risk lookup failed: %s", e)
    return None
