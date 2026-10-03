"""LLM gateway — the only module that talks to Gemini.

Properties (lessons carried over from TESSA, plus fixes):
  * provider-agnostic call surface: engines never import the SDK
  * model pool with a per-model cooldown (primary = SAARTHI_MODEL, optional fallbacks)
  * disk cache for deterministic content (explanations), keyed by model + prompt + schema
  * FAIL CLOSED: when no model is reachable, `LLMUnavailable` is raised. Callers that grade learners must
    not invent a result. (Callers that only paraphrase curated text may fall back to the curated text.)
  * `SAARTHI_LLM_MODE=fake` swaps in a keyword grader for offline development; `/health` then reports
    `llm_mode: fake` and the UI shows a red "TEST LLM" banner. Never use it in the demo.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Callable, Optional

from ..config import DATA_DIR, settings

log = logging.getLogger("saarthi.llm")

PROMPT_VERSION = "v1"
_client = None
_cooldown_until: dict[str, float] = {}
_calls = {"ok": 0, "error": 0, "cache_hit": 0}
_last_error: Optional[str] = None


class LLMUnavailable(RuntimeError):
    pass


def mode() -> str:
    return settings.llm_mode


def available() -> bool:
    return settings.llm_mode == "fake" or bool(settings.gemini_api_key)


def status() -> dict[str, Any]:
    return {"mode": settings.llm_mode, "available": available(), "model": settings.model,
            "fallbacks": settings.llm_models[1:], "calls": dict(_calls), "last_error": _last_error,
            "prompt_version": PROMPT_VERSION}


def _get_client():
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise LLMUnavailable("GEMINI_API_KEY is not set")
        from google import genai
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _cache_path(key: str):
    d = DATA_DIR / "llm_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def _key(model: str, system: str, prompt: str, schema: Any) -> str:
    h = hashlib.sha256()
    h.update(f"{PROMPT_VERSION}|{model}|{system}|{prompt}|{json.dumps(schema, sort_keys=True, default=str)}".encode())
    return h.hexdigest()[:40]


def _models() -> list[str]:
    now = time.monotonic()
    pool = [m for m in settings.llm_models if _cooldown_until.get(m, 0) <= now]
    return pool or settings.llm_models[:1]


def _thinking_cfg(model: str, types):
    """Keep reasoning short: thinking tokens count against max_output_tokens and add latency to every voice turn."""
    try:
        if model.startswith("gemini-3"):
            return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
        if model.startswith("gemini-2.5") and "pro" not in model:
            return types.ThinkingConfig(thinking_budget=0)
    except Exception:  # noqa: BLE001 - older SDKs
        return None
    return None


def _generate(system: str, prompt: str, *, schema: Optional[dict], max_tokens: int, temperature: float,
              parse: Optional[Callable[[str], Any]] = None) -> tuple[Any, str]:
    """Try each model in the pool; a model counts as failed if the call errors OR its output does not parse."""
    global _last_error
    from google.genai import types
    client = _get_client()
    last: Optional[Exception] = None
    for model in _models():
        for use_thinking in (True, False):
            try:
                cfg_kwargs: dict[str, Any] = {
                    "system_instruction": system, "max_output_tokens": max_tokens, "temperature": temperature,
                    "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
                }
                if schema is not None:
                    cfg_kwargs.update(response_mime_type="application/json", response_json_schema=schema)
                tc = _thinking_cfg(model, types) if use_thinking else None
                if tc is not None:
                    cfg_kwargs["thinking_config"] = tc
                elif use_thinking is False and _thinking_cfg(model, types) is None:
                    pass
                resp = client.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(**cfg_kwargs))
                text = (resp.text or "").strip()
                if not text:
                    raise RuntimeError("empty response")
                value = parse(text) if parse else text
                _calls["ok"] += 1
                return value, model
            except Exception as exc:  # noqa: BLE001 - try without thinking once, then the next model
                last = exc
                msg = str(exc).lower()
                if use_thinking and _thinking_cfg(model, types) is not None and ("thinking" in msg or "budget" in msg or "invalid argument" in msg):
                    continue  # the model rejected the thinking setting: retry the same model without it
                _calls["error"] += 1
                _last_error = f"{model}: {type(exc).__name__}: {str(exc)[:200]}"
                _cooldown_until[model] = time.monotonic() + 20
                log.warning("LLM call failed on %s: %s", model, _last_error)
                break
    raise LLMUnavailable(_last_error or "no model available") from last


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a == -1 or b == -1:
            raise ValueError("model did not return JSON")
        data = json.loads(text[a:b + 1])
    if not isinstance(data, dict):
        raise ValueError("model returned a non-object")
    return data


def generate_json(task: str, system: str, prompt: str, schema: dict, *, fake: Optional[Callable[[], dict]] = None,
                  cache: bool = False, max_tokens: int = 2048, temperature: float = 0.1) -> dict[str, Any]:
    if settings.llm_mode == "fake":
        if fake is None:
            raise LLMUnavailable(f"fake mode has no handler for task '{task}'")
        return fake()
    if not available():
        raise LLMUnavailable("no GEMINI_API_KEY configured")
    ck = _key(settings.model, system, prompt, schema)
    path = _cache_path(ck) if cache else None
    if path and path.exists():
        _calls["cache_hit"] += 1
        return json.loads(path.read_text(encoding="utf-8"))
    data, model = _generate(system, prompt, schema=schema, max_tokens=max_tokens, temperature=temperature, parse=_parse_json_object)
    data["_model"] = model
    if path:
        path.write_text(json.dumps(data), encoding="utf-8")
    return data


def generate_text(task: str, system: str, prompt: str, *, fake: Optional[Callable[[], str]] = None,
                  cache: bool = False, max_tokens: int = 1200, temperature: float = 0.3) -> str:
    if settings.llm_mode == "fake":
        if fake is None:
            raise LLMUnavailable(f"fake mode has no handler for task '{task}'")
        return fake()
    if not available():
        raise LLMUnavailable("no GEMINI_API_KEY configured")
    ck = _key(settings.model, system, prompt, None)
    path = _cache_path(ck) if cache else None
    if path and path.exists():
        _calls["cache_hit"] += 1
        return json.loads(path.read_text(encoding="utf-8"))["text"]
    text, _ = _generate(system, prompt, schema=None, max_tokens=max_tokens, temperature=temperature)
    if path:
        path.write_text(json.dumps({"text": text}), encoding="utf-8")
    return text
