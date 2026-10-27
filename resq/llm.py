"""The only door to the language models (AGENTS.md rule 2).

Talks to an OpenAI-compatible API: Meterless Nightshift by default, direct
NVIDIA only in development (both are set in .env). Two lanes:

- fast: thinking off, short answers, temperature 0 (Reconciler, Risk Analyst, Explainer).
  At 0.2 the Reconciler decided contested objects differently between runs (T11 open vs
  uncertain), which changed the plan downstream; these are classifications, not prose,
  so the lane is deterministic.
- deep: larger budget (Planner, Critic), also temperature 0. At 0.2 the Planner
  returned different tier decisions for the same scenario, so a demo could not be
  rehearsed; measured on Nemotron 3 Ultra, temperature 0 was no slower.
  Thinking only if LANE_DEEP_THINKING=true: measured on the same model it made the
  decisions stable but took 53 s per call against 11 s, and one call in three
  exceeded the 90 s timeout, so it stays off.

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
    "fast": {"thinking": False, "max_tokens": 2000, "temperature": 0.0},
    "deep": {"thinking": False, "max_tokens": 8000, "temperature": 0.0},
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
    thinking = settings.lane_deep_thinking if lane == "deep" else config["thinking"]
    model = settings.lane_model(lane)
    request = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or config["max_tokens"],
        "temperature": config["temperature"],
        "extra_body": {"chat_template_kwargs": {"enable_thinking": thinking}},
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


PRIMARY_PROVIDER_CHECK = "meterless primary provider"


def check(lanes: tuple[str, ...] = ("fast", "deep")) -> list[tuple[str, bool, str]]:
    """Meterless Runtime checks: connection, authorization, model discovery and one text request per lane.

    Returns (check, ok, detail) rows. Never prints or returns the token.
    """
    settings = get_settings()
    rows: list[tuple[str, bool, str]] = []
    host = settings.model_base_url.split("//")[-1].split("/")[0] if settings.model_base_url else "-"
    rows.append(("provider", bool(settings.model_base_url and settings.model_api_key),
                 f"{settings.model_provider} at {host}"))
    if not rows[-1][1]:
        rows.append(("configuration", False, "set METERLESS_BASE_URL and METERLESS_RUNTIME_TOKEN (from the Nightshift Console)"))
        return rows
    rows.append((PRIMARY_PROVIDER_CHECK, settings.model_provider == "Meterless Nightshift",
                 "requests go through Nightshift" if settings.model_provider == "Meterless Nightshift"
                 else "not Meterless: fine for development, but the demo must run on Nightshift (AGENTS.md rule 2)"))
    try:
        models = [m.id for m in _client().models.list()]
    except APIError as error:
        status = getattr(error, "status_code", None)
        if status == 401:
            detail = "token rejected (401): copy the Runtime token again from the Nightshift Console"
        elif status == 404:
            detail = "404: the base URL must end in /v1"
        else:
            detail = f"{type(error).__name__}: {str(error)[:120]}"
        rows.append(("connection + authorization", False, detail))
        return rows
    except Exception as error:  # noqa: BLE001 - unreachable host, DNS, TLS: report, do not crash
        rows.append(("connection + authorization", False, f"unreachable: {type(error).__name__}"))
        return rows
    rows.append(("connection + authorization", True, "GET /v1/models answered"))
    rows.append(("model discovery", bool(models), f"{len(models)} models" + (f", e.g. {', '.join(models[:3])}" if models else "")))
    for lane in lanes:
        model = settings.lane_model(lane)
        listed = model in models
        rows.append((f"{lane} lane model", listed, model + ("" if listed else " (not listed by the Runtime)")))
        try:
            reply = chat([{"role": "user", "content": "Reply with the single word: ready"}], lane=lane, max_tokens=50)
        except LLMError as error:
            rows.append((f"{lane} lane request", False, str(error)[:160]))
            continue
        ok = bool(reply["content"])
        rows.append((f"{lane} lane request", ok,
                     f"{reply['model']} answered in {reply['duration_ms']} ms" if ok else "empty reply (thinking not turned off?)"))
    return rows


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m resq.llm", description="Check the Meterless Nightshift provider")
    parser.add_argument("--check", action="store_true", help="connection, authorization, discovery and a request per lane")
    parser.add_argument("--lane", choices=sorted(LANES), action="append", help="only this lane (repeatable)")
    args = parser.parse_args(argv)
    if not args.check:
        parser.print_help()
        return 0
    rows = check(tuple(args.lane or ("fast", "deep")))
    for name, ok, detail in rows:
        mark = "PASS" if ok else ("WARN" if name == PRIMARY_PROVIDER_CHECK else "FAIL")
        print(f"{mark}  {name:28} {detail}")
    # Direct NVIDIA is allowed in development, so it warns instead of failing the check.
    return 0 if all(ok for name, ok, _ in rows if name != PRIMARY_PROVIDER_CHECK) else 1


if __name__ == "__main__":
    raise SystemExit(main())
