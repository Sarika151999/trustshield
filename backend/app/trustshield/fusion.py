"""Stage 4 - risk fusion + deterministic policy. Gemini never makes the decision."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .schemas import Signal

POLICY_VERSION = "policy_v1"


@dataclass(frozen=True)
class FusionConfig:
    use_behaviour: bool = True
    use_content: bool = True
    use_intel: bool = True
    bias: float = -3.2
    w_b: float = 3.0
    w_c: float = 2.8
    w_i: float = 3.5
    w_bc: float = 2.0   # interaction: risky behaviour AND a scam script is much worse than either alone
    w_l: float = -1.2   # evidence corroborating a genuine purpose lowers risk
    warn: float = 0.35
    hold: float = 0.70
    warn_vulnerable: float = 0.30
    hold_vulnerable: float = 0.62


FULL = FusionConfig()
HARD_HOLD = {"beneficiary_known_mule", "safe_account_transfer", "remote_access_request"}


def noisy_or(xs: list[float]) -> float:
    p = 1.0
    for x in xs:
        p *= 1.0 - max(0.0, min(x, 1.0))
    return 1.0 - p


def components(signals: list[Signal], cfg: FusionConfig = FULL) -> dict[str, float]:
    by = {"behaviour": [], "content": [], "intel": [], "legit": []}
    for s in signals:
        by[s.component].append(s.strength)
    return {
        "behaviour": noisy_or(by["behaviour"]) if cfg.use_behaviour else 0.0,
        "content": noisy_or(by["content"]) if cfg.use_content else 0.0,
        "intel": min(1.0, noisy_or(by["intel"])) if cfg.use_intel else 0.0,
        "legit": max(by["legit"], default=0.0) if cfg.use_content else 0.0,
    }


def logit_of(c: dict[str, float], cfg: FusionConfig = FULL) -> float:
    return (cfg.bias + cfg.w_b * c["behaviour"] + cfg.w_c * c["content"] + cfg.w_i * c["intel"]
            + cfg.w_bc * c["behaviour"] * c["content"] + cfg.w_l * c["legit"])


def risk_of(c: dict[str, float], cfg: FusionConfig = FULL) -> float:
    return 1.0 / (1.0 + math.exp(-logit_of(c, cfg)))


def score(signals: list[Signal], cfg: FusionConfig = FULL) -> tuple[float, dict[str, float]]:
    c = components(signals, cfg)
    return risk_of(c, cfg), c


def attribute(signals: list[Signal], cfg: FusionConfig = FULL) -> list[Signal]:
    """Contribution of each signal in log-odds points.

    1) exact Shapley values over the 4 components (behaviour, content, intel, legit) - sums to logit - bias;
    2) each component's share is split across its signals in proportion to -ln(1 - strength), i.e. each
       signal's share of the noisy-OR evidence. Fair even when components saturate."""
    from itertools import permutations

    comps = components(signals, cfg)
    names = list(comps)

    def v(subset: set[str]) -> float:
        return logit_of({k: (comps[k] if k in subset else 0.0) for k in names}, cfg)

    shap = {k: 0.0 for k in names}
    perms = list(permutations(names))
    for order in perms:
        seen: set[str] = set()
        for k in order:
            shap[k] += v(seen | {k}) - v(seen)
            seen.add(k)
    shap = {k: x / len(perms) for k, x in shap.items()}

    out = []
    for comp in names:
        members = [s for s in signals if s.component == comp]
        weights = [-math.log(max(1e-6, 1.0 - min(s.strength, 0.999))) for s in members]
        total = sum(weights) or 1.0
        for s, w in zip(members, weights):
            out.append(s.model_copy(update={"contribution": round(shap[comp] * w / total, 3)}))
    return sorted(out, key=lambda s: abs(s.contribution), reverse=True)


def decide(risk: float, signals: list[Signal], vulnerable: bool, cfg: FusionConfig = FULL) -> tuple[str, str | None]:
    """Returns (decision, hard_rule_code)."""
    for s in signals:
        if s.code in HARD_HOLD and s.strength >= 0.5 and (
                (s.component == "intel" and cfg.use_intel) or (s.component == "content" and cfg.use_content)):
            return "HOLD", s.code
    warn, hold = (cfg.warn_vulnerable, cfg.hold_vulnerable) if vulnerable else (cfg.warn, cfg.hold)
    if risk >= hold:
        return "HOLD", None
    if risk >= warn:
        return "WARN", None
    return "PASS", None
