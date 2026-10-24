"""JSONL trace: one line per agent step in logs/trace_<run_id>.jsonl (AGENTS.md section 7).

Never pass secrets here: entries hold short summaries of inputs and outputs only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from resq.config import get_settings

SUMMARY_CHARS = 600


def _short(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= SUMMARY_CHARS else text[:SUMMARY_CHARS] + "…"


def record(run_id: str, agent: str, input_summary, output_summary, lane: str = "", model: str = "",
           duration_ms: int = 0, iteration: int = 0, **extra) -> dict:
    """Append one trace line and return it (so the graph can also keep it in its state)."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_id,
        "agent": agent,
        "input_summary": _short(input_summary),
        "output_summary": _short(output_summary),
        "lane": lane,
        "model": model,
        "duration_ms": duration_ms,
        "iteration": iteration,
        **extra,
    }
    logs_dir = get_settings().logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    with (logs_dir / f"trace_{run_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    return entry
