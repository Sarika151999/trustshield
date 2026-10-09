from __future__ import annotations

import time
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Timer:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._last = self._t0
        self.marks: dict[str, int] = {}

    def mark(self, name: str) -> None:
        t = time.perf_counter()
        self.marks[name] = round((t - self._last) * 1000)
        self._last = t

    def total(self) -> int:
        return round((time.perf_counter() - self._t0) * 1000)


def fmt_inr(x: float, signed: bool = False) -> str:
    """Indian-style compact money: ₹3.1L, ₹1.24 Cr, ₹85,000."""
    neg = x < 0
    a = abs(x)
    if a >= 1e7:
        s = f"₹{a / 1e7:.2f} Cr"
    elif a >= 1e5:
        s = f"₹{a / 1e5:.1f}L"
    else:
        n = f"{a:.0f}"
        if len(n) > 3:
            head, tail = n[:-3], n[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            n = ",".join(groups) + "," + tail
        s = f"₹{n}"
    if neg:
        return "-" + s
    return ("+" + s) if signed else s
