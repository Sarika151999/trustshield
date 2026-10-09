"""Thin wrapper over the google-genai SDK.

* `structured()` returns a validated Pydantic object (JSON-schema constrained output).
* `chat_step()` runs one function-calling step for agents.
* Every call is timed and recorded in an in-memory ring buffer shown in the UI.
* GEMINI_BACKEND=mock disables live calls; callers then use their deterministic fallback.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from typing import Any, TypeVar

from pydantic import BaseModel

from ..config import settings

log = logging.getLogger("gemini")
T = TypeVar("T", bound=BaseModel)


class GeminiUnavailable(RuntimeError):
    pass


class _CallLog:
    def __init__(self, size: int = 200) -> None:
        self._items: deque[dict] = deque(maxlen=size)
        self._lock = threading.Lock()

    def add(self, item: dict) -> None:
        with self._lock:
            self._items.appendleft(item)

    def recent(self, n: int = 50) -> list[dict]:
        with self._lock:
            return list(self._items)[:n]


call_log = _CallLog()


class Gemini:
    def __init__(self) -> None:
        self.backend = settings.gemini_backend
        self._client = None
        if self.backend == "vertex":
            from google import genai

            self._client = genai.Client(vertexai=True, project=settings.project, location=settings.vertex_location)
        elif self.backend == "apikey":
            from google import genai

            self._client = genai.Client(api_key=settings.gemini_api_key)

    @property
    def live(self) -> bool:
        return self._client is not None

    # ------------------------------------------------------------------ structured
    def structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        media: list[tuple[bytes, str]] | None = None,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        purpose: str = "",
    ) -> T:
        if not self.live:
            raise GeminiUnavailable("mock backend")
        from google.genai import types

        model = model or settings.fast_model
        parts: list[Any] = [types.Part.from_bytes(data=b, mime_type=m) for b, m in (media or [])]
        parts.append(prompt)
        last_err: Exception | None = None
        for attempt in range(3):
            t0 = time.perf_counter()
            try:
                resp = self._client.models.generate_content(
                    model=model,
                    contents=parts,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=temperature,
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )
                parsed = resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate_json(resp.text)
                self._record(model, purpose or schema.__name__, t0, resp, ok=True)
                return parsed
            except Exception as e:  # noqa: BLE001 - retry any transport/validation error
                last_err = e
                self._record(model, purpose or schema.__name__, t0, None, ok=False, error=str(e)[:300])
                time.sleep(0.4 * (2**attempt))
        raise GeminiUnavailable(f"structured call failed: {last_err}")

    # ------------------------------------------------------------------ text
    def text(self, prompt: str, *, system: str | None = None, model: str | None = None,
             temperature: float = 0.3, purpose: str = "text") -> str:
        if not self.live:
            raise GeminiUnavailable("mock backend")
        from google.genai import types

        model = model or settings.fast_model
        t0 = time.perf_counter()
        try:
            resp = self._client.models.generate_content(
                model=model, contents=[prompt],
                config=types.GenerateContentConfig(system_instruction=system, temperature=temperature),
            )
            self._record(model, purpose, t0, resp, ok=True)
            return resp.text or ""
        except Exception as e:  # noqa: BLE001
            self._record(model, purpose, t0, None, ok=False, error=str(e)[:300])
            raise GeminiUnavailable(str(e)) from e

    # ------------------------------------------------------------------ agents
    def chat_step(self, contents: list, *, system: str, tools: list[dict], model: str | None = None,
                  temperature: float = 0.2, purpose: str = "agent"):
        """One model turn with function declarations. Returns the raw response."""
        if not self.live:
            raise GeminiUnavailable("mock backend")
        from google.genai import types

        model = model or settings.fast_model
        decls = [types.FunctionDeclaration(name=t["name"], description=t["description"],
                                           parameters_json_schema=t["parameters"]) for t in tools]
        t0 = time.perf_counter()
        try:
            resp = self._client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    tools=[types.Tool(function_declarations=decls)],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            self._record(model, purpose, t0, resp, ok=True)
            return resp
        except Exception as e:  # noqa: BLE001
            self._record(model, purpose, t0, None, ok=False, error=str(e)[:300])
            raise GeminiUnavailable(str(e)) from e

    # ------------------------------------------------------------------ telemetry
    def _record(self, model: str, purpose: str, t0: float, resp: Any, ok: bool, error: str | None = None) -> None:
        ms = round((time.perf_counter() - t0) * 1000)
        usage = getattr(resp, "usage_metadata", None)
        item = {
            "ts": time.time(), "model": model, "purpose": purpose, "latency_ms": ms, "ok": ok,
            "in_tokens": getattr(usage, "prompt_token_count", None),
            "out_tokens": getattr(usage, "candidates_token_count", None),
            "error": error,
        }
        call_log.add(item)
        log.info(json.dumps({"event": "gemini_call", **item}))


_instance: Gemini | None = None


def gemini() -> Gemini:
    global _instance
    if _instance is None:
        _instance = Gemini()
    return _instance
