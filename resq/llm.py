"""The only door to the language models (AGENTS.md rule 2).

Talks to an OpenAI-compatible API: Meterless Nightshift by default, direct
NVIDIA only in development (both are set in .env). Two lanes:

- fast: thinking off, short answers (Intake, Reconciler, Risk Analyst, Explainer)
- deep: thinking on, larger budget (Planner, Critic)

Nemotron 3.5 thinks by default; with a small max_tokens budget the reasoning
consumes every token and `content` comes back empty, so the fast lane turns it
off through `chat_template_kwargs`. TODO(verify): that Nightshift forwards it.
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache

from openai import APIError, APITimeoutError, OpenAI

from resq.config import get_settings

LANES = {
    "fast": {"thinking": False, "max_tokens": 2000, "temperature": 0.2},
    "deep": {"thinking": True, "max_tokens": 12000, "temperature": 0.2},
}
METERLESS_HEADERS = {"meterless-app": "resq-ai", "meterless-scope": "user"}
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMError(RuntimeError):
    """The model failed, timed out or returned something unusable."""


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    settings = get_settings()
    if not (settings.model_base_url and settings.model_api_key):
        raise LLMError("model is not configured: set MODEL_BASE_URL and MODEL_API_KEY in .env")
    return OpenAI(
        base_url=settings.model_base_url,
        api_key=settings.model_api_key,
        timeout=settings.model_timeout_s,
        max_retries=0,  # retries are handled here, bounded by AGENTS.md section 7
        default_headers=METERLESS_HEADERS,
    )


def chat(messages: list[dict], lane: str = "fast", tools: list | None = None, max_tokens: int | None = None) -> dict:
    """One chat completion. Returns content, reasoning, model, lane, usage and duration_ms."""
    if lane not in LANES:
        raise ValueError(f"unknown lane: {lane!r} (expected 'fast' or 'deep')")
    settings = get_settings()
    config = LANES[lane]
    model = settings.lane_model(lane)
    request = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or config["max_tokens"],
        "temperature": config["temperature"],
        "extra_body": {"chat_template_kwargs": {"enable_thinking": config["thinking"]}},
    }
    if tools:
        request["tools"] = tools

    last_error = ""
    for attempt in range(settings.max_retries + 1):
        started = time.monotonic()
        try:
            response = _client().chat.completions.create(**request)
        except (APIError, APITimeoutError) as error:
            last_error = f"{type(error).__name__}: {str(error)[:160]}"
            if attempt < settings.max_retries:
                time.sleep(2 * (attempt + 1))
            continue
        choice = response.choices[0]
        extra = choice.message.model_extra or {}
        return {
            "content": (choice.message.content or "").strip(),
            "reasoning": extra.get("reasoning_content") or extra.get("reasoning") or "",
            "tool_calls": [call.model_dump() for call in (choice.message.tool_calls or [])],
            "finish_reason": choice.finish_reason,
            "model": response.model or model,
            "lane": lane,
            "usage": response.usage.model_dump() if response.usage else {},
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    raise LLMError(f"model call failed after {settings.max_retries + 1} attempts: {last_error}")


def parse_json(text: str):
    """Parse a JSON object or array from a reply, tolerating code fences and surrounding prose."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1]
    if not starts:
        raise LLMError(f"no JSON in model reply: {text[:160]!r}")
    start = min(starts)
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as error:
        raise LLMError(f"invalid JSON in model reply: {error}") from error


def chat_json(messages: list[dict], lane: str = "fast", max_tokens: int | None = None) -> tuple[object, dict]:
    """Chat and parse JSON. One repair round if the first reply is not valid JSON."""
    reply = chat(messages, lane=lane, max_tokens=max_tokens)
    try:
        return parse_json(reply["content"]), reply
    except LLMError as error:
        repair = messages + [
            {"role": "assistant", "content": reply["content"][:4000]},
            {"role": "user", "content": f"That was not valid JSON ({error}). Reply again with ONLY the JSON, no prose."},
        ]
        second = chat(repair, lane=lane, max_tokens=max_tokens)
        second["duration_ms"] += reply["duration_ms"]
        return parse_json(second["content"]), second
