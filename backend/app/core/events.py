"""Event bus: publishes domain events to Pub/Sub (cloud) or an in-memory log (local).

On GCP each topic has a BigQuery subscription, so events land in BigQuery with no extra code
(see infra/setup.sh).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque

from ..config import settings

log = logging.getLogger("events")

TOPICS = {
    "assessment.completed": "ts-assessment-completed",
    "case.resolved": "ts-case-resolved",
    "intel.shared": "ts-intel-shared",
    "cfo.forecast.completed": "cfo-forecast-completed",
    "cfo.scenario.run": "cfo-scenario-run",
    "cfo.document.confirmed": "cfo-document-confirmed",
}


class EventBus:
    def __init__(self) -> None:
        self._recent: deque[dict] = deque(maxlen=300)
        self._lock = threading.Lock()
        self._publisher = None
        if settings.events_backend == "pubsub":
            from google.cloud import pubsub_v1

            self._publisher = pubsub_v1.PublisherClient()

    def publish(self, event: str, payload: dict) -> None:
        envelope = {"event": event, "ts": time.time(), "payload": payload}
        with self._lock:
            self._recent.appendleft(envelope)
        if self._publisher is not None:
            topic = self._publisher.topic_path(settings.project, TOPICS.get(event, event.replace(".", "-")))
            try:
                self._publisher.publish(topic, json.dumps(payload, default=str).encode(), event=event)
            except Exception as e:  # noqa: BLE001 - events must never break the request path
                log.warning("pubsub publish failed: %s", e)
        log.info(json.dumps({"event": "domain_event", "name": event}))

    def recent(self, n: int = 50, prefix: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._recent)
        if prefix:
            items = [e for e in items if e["event"].startswith(prefix)]
        return items[:n]


_bus: EventBus | None = None


def bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
