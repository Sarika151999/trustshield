"""Stage 1 - deterministic behavioural features (no ML, fully explainable)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..core.util import fmt_inr
from .schemas import PaymentContext, Signal

IST = timezone(timedelta(hours=5, minutes=30))


def behaviour_signals(amount: float, ben: dict, profile: dict, ctx: PaymentContext,
                      recent_outgoing_1h: int = 0, now: datetime | None = None) -> list[Signal]:
    now = now or datetime.now(timezone.utc)
    st = profile["stats"]
    out: list[Signal] = []

    def add(code: str, strength: float, text: str) -> None:
        out.append(Signal(code=code, component="behaviour", strength=round(min(strength, 0.95), 3), text=text))

    z = (amount - st["mean_90d"]) / max(st["std_90d"], 1.0)
    if z > 2:
        add("amount_z", 0.15 + 0.08 * z,
            f"{fmt_inr(amount)} is {amount / max(st['mean_90d'], 1):.1f}x your typical payment of {fmt_inr(st['mean_90d'])}")
    if amount > 1.5 * st["max_90d"]:
        add("amount_vs_max", 0.3, f"Larger than any payment in the last 90 days (max {fmt_inr(st['max_90d'])})")

    added = datetime.fromisoformat(ben["added_at"])
    age = now - added
    if age < timedelta(hours=1):
        add("new_beneficiary", 0.6, f"Payee added {max(1, int(age.total_seconds() // 60))} minutes ago")
    elif age < timedelta(hours=24):
        add("new_beneficiary", 0.45, f"Payee added {int(age.total_seconds() // 3600)} hours ago")
    elif age < timedelta(days=7):
        add("new_beneficiary", 0.2, f"Payee added {age.days} days ago")
    if ben.get("prior_payment_count", 0) == 0:
        add("first_payment_to_ben", 0.25, "First ever payment to this payee")

    if st["balance"] > 0:
        drain = amount / st["balance"]
        if drain > 0.7:
            add("balance_drain", 0.4, f"Uses {drain:.0%} of your available balance")
        elif drain > 0.5:
            add("balance_drain", 0.25, f"Uses {drain:.0%} of your available balance")

    if recent_outgoing_1h >= 2:
        add("velocity_1h", 0.3, f"{recent_outgoing_1h} other outgoing payments in the last hour")

    hour = ctx.hour if ctx.hour is not None else now.astimezone(IST).hour
    if hour < st["p05_hour"] - 1 or hour > st["p95_hour"] + 1:
        add("odd_hour", 0.15, f"Unusual time of day for you ({hour:02d}:00)")

    if ctx.new_device:
        add("device_change", 0.3, "Payment from a device first seen in the last 7 days")
    if ctx.active_call:
        add("active_call", 0.35, "You are on a phone call while making this payment")

    verified = (ben.get("verified_name") or "").lower()
    if verified and ben.get("display_name") and verified not in ben["display_name"].lower():
        add("payee_name_mismatch", 0.4, f"Account holder name '{ben['verified_name']}' does not match the payee name")
    return out
