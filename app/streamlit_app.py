"""RESQ AI Streamlit dashboard.

Run with:

    streamlit run app/streamlit_app.py

The default example mode is fully offline. Live mode calls the public
``resq.run.execute`` contract and then reads the resulting World Model state.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Iterable

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "output_examples"
SAMPLE_DIR = ROOT / "data" / "sample"

EXAMPLE_RUNS = {
    "baseline": {
        "label": "v1 · Baseline",
        "plan": "01_baseline_plan.json",
        "report": "01_baseline_report.md",
        "trace": "01_baseline_trace.jsonl",
        "request_type": "plan",
        "blocked": (),
    },
    "blocked": {
        "label": "v2 · T6 blocked",
        "plan": "02_block_T6_plan.json",
        "report": "02_block_T6_report.md",
        "trace": "02_block_T6_trace.jsonl",
        "request_type": "event",
        "blocked": ("T6",),
    },
}

STATUS_META = {
    "open": ("Open", "#70C1A5", ""),
    "damaged": ("Open · damaged", "#70C1A5", "5 4"),
    "flooded": ("Flooded", "#FFB400", "8 5"),
    "passable_4x4": ("Flooded · 4x4 only", "#FFB400", "8 5"),
    "uncertain": ("Flooded · uncertain", "#FFB400", "3 5"),
    "closed": ("Blocked · closed", "#D32F2F", "2 4"),
    "blocked": ("Blocked", "#D32F2F", "2 4"),
}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def plan_to_dict(plan: Any) -> dict[str, Any]:
    """Normalize a Pydantic plan or an example JSON object."""
    if plan is None:
        return {}
    if hasattr(plan, "model_dump"):
        return plan.model_dump()
    return dict(plan)


def load_example_run(key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load one committed demo run and its schematic map state."""
    config = EXAMPLE_RUNS[key]
    plan = _read_json(EXAMPLES_DIR / config["plan"])
    result = {
        "run_id": f"example-{key}",
        "request_type": config["request_type"],
        "plan": plan,
        "report": (EXAMPLES_DIR / config["report"]).read_text(encoding="utf-8"),
        "trace": _read_jsonl(EXAMPLES_DIR / config["trace"]),
        "escalated": bool(plan.get("escalated")),
        "reviews": [],
    }
    return result, load_sample_map(config["blocked"])


def load_sample_map(blocked_segments: Iterable[str] = ()) -> dict[str, Any]:
    """Build map state from the committed sample tables for example mode."""
    blocked = set(blocked_segments)
    nodes = {row["id"]: row for row in _read_csv(SAMPLE_DIR / "road_nodes.csv")}
    segments = {}
    for row in _read_csv(SAMPLE_DIR / "road_segments.csv"):
        segment = dict(row)
        segment["status"] = "blocked" if row["id"] in blocked else row["official_status"]
        segments[row["id"]] = segment
    return {"road_nodes": nodes, "road_segments": segments}


def escalation_reasons(plan: Any) -> list[str]:
    """Return the exact P8.3 risks that justify human escalation."""
    data = plan_to_dict(plan)
    return [str(risk) for risk in data.get("risks", []) if str(risk).startswith("P8.3")]


def assignment_rows(plan: Any) -> list[dict[str, Any]]:
    """Return presentation-ready assignment rows without changing quantities."""
    rows = []
    for item in plan_to_dict(plan).get("assignments", []):
        assignment = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        rows.append(
            {
                "priority": assignment.get("priority", ""),
                "community": assignment.get("community_id", ""),
                "resource": str(assignment.get("resource", "")).replace("_", " ").title(),
                "quantity": assignment.get("quantity", ""),
                "vehicle": assignment.get("vehicle_id", ""),
                "route": " · ".join(assignment.get("route", [])) or "Same road node",
                "reason": assignment.get("reason", ""),
            }
        )
    return rows


def trace_rows(trace: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the operational trace fields requested by the dashboard."""
    return [
        {
            "agent": str(step.get("agent", "unknown")).replace("_", " ").title(),
            "round": step.get("iteration", 0),
            "duration": f"{int(step.get('duration_ms') or 0):,} ms",
            "lane": step.get("lane") or "rules",
            "summary": step.get("output_summary") or "No summary returned.",
        }
        for step in trace
    ]


def _status(segment: dict[str, Any]) -> str:
    return str(segment.get("status") or segment.get("official_status") or "open").lower()


def build_map_svg(map_state: dict[str, Any], active_segments: Iterable[str] = ()) -> str:
    """Render an offline SVG road map with text and line-style status cues."""
    nodes = map_state.get("road_nodes", {})
    segments = map_state.get("road_segments", {})
    if not nodes or not segments:
        return '<div class="empty-state">Road geometry is not available.</div>'

    points = {
        node_id: (float(node["lon"]), float(node["lat"]))
        for node_id, node in nodes.items()
        if node.get("lon") not in (None, "") and node.get("lat") not in (None, "")
    }
    if not points:
        return '<div class="empty-state">Road geometry is not available.</div>'

    width, height, pad = 760, 410, 34
    longitudes = [point[0] for point in points.values()]
    latitudes = [point[1] for point in points.values()]
    lon_span = max(max(longitudes) - min(longitudes), 0.001)
    lat_span = max(max(latitudes) - min(latitudes), 0.001)

    def project(point: tuple[float, float]) -> tuple[float, float]:
        lon, lat = point
        x = pad + (lon - min(longitudes)) / lon_span * (width - 2 * pad)
        y = height - pad - (lat - min(latitudes)) / lat_span * (height - 2 * pad)
        return x, y

    active = set(active_segments)
    lines = []
    labels = []
    for segment_id, segment in segments.items():
        if segment.get("origin") not in points or segment.get("destination") not in points:
            continue
        x1, y1 = project(points[segment["origin"]])
        x2, y2 = project(points[segment["destination"]])
        status = _status(segment)
        label, color, dash = STATUS_META.get(status, (f"Unknown · {status}", "#8A9598", "2 5"))
        stroke_width = 7 if segment_id in active else 4
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        safe_id = html.escape(str(segment_id))
        lines.append(
            f'<g><title>{safe_id}: {html.escape(label)}</title>'
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{stroke_width}"{dash_attr} stroke-linecap="round"/></g>'
        )
        labels.append(
            f'<text x="{(x1 + x2) / 2:.1f}" y="{(y1 + y2) / 2 - 6:.1f}" '
            f'text-anchor="middle">{safe_id}</text>'
        )

    node_marks = []
    for node_id, point in points.items():
        x, y = project(point)
        safe_id = html.escape(str(node_id))
        node_marks.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5"/><text class="node-label" '
            f'x="{x + 8:.1f}" y="{y + 4:.1f}">{safe_id}</text>'
        )

    return (
        '<div class="map-frame" role="img" aria-label="Road network map with open, flooded, and blocked segments">'
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="100%" height="100%" fill="#101516"/>'
        + "".join(lines)
        + "".join(labels)
        + "".join(node_marks)
        + "</svg>"
        '<div class="map-legend"><span><i class="open"></i>Open</span>'
        '<span><i class="flooded"></i>Flooded / limited</span>'
        '<span><i class="blocked"></i>Blocked / closed</span></div></div>'
    )


def render_assignment_table(plan: Any, animate: bool = False) -> str:
    """Return an accessible HTML assignment table in dispatch-board styling."""
    rows = assignment_rows(plan)
    if not rows:
        return '<div class="empty-state">No assignments were returned for this plan.</div>'
    body = []
    for index, row in enumerate(rows):
        body.append(
            f'<tr style="--row-index:{min(index, 12)}">'
            f'<td class="priority">{html.escape(str(row["priority"]))}</td>'
            f'<td><strong>{html.escape(str(row["community"]))}</strong></td>'
            f'<td>{html.escape(str(row["resource"]))}</td>'
            f'<td class="quantity">{html.escape(str(row["quantity"]))}</td>'
            f'<td>{html.escape(str(row["vehicle"]))}</td>'
            f'<td class="route">{html.escape(str(row["route"]))}</td>'
            f'<td class="reason">{html.escape(str(row["reason"]))}</td></tr>'
        )
    signal_class = " signal" if animate else ""
    return (
        '<div class="table-shell"><div class="scroll-hint">Keep priority and community visible while scrolling routes</div>'
        f'<div class="table-scroll"><table class="dispatch-table{signal_class}"><thead><tr>'
        '<th scope="col">Priority</th><th scope="col">Community</th><th scope="col">Resource</th>'
        '<th scope="col">Quantity</th><th scope="col">Vehicle</th><th scope="col">Route</th>'
        '<th scope="col">Reason</th></tr></thead><tbody>'
        + "".join(body)
        + "</tbody></table></div></div>"
    )


def render_trace_table(trace: Iterable[dict[str, Any]]) -> str:
    rows = trace_rows(trace)
    if not rows:
        return '<div class="empty-state">No trace steps were returned for this run.</div>'
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f'<td><strong>{html.escape(str(row["agent"]))}</strong></td>'
            f'<td>{html.escape(str(row["round"]))}</td>'
            f'<td>{html.escape(str(row["duration"]))}</td>'
            f'<td>{html.escape(str(row["lane"]))}</td>'
            f'<td class="reason">{html.escape(str(row["summary"]))}</td>'
            "</tr>"
        )
    return (
        '<div class="table-scroll trace-scroll"><table class="dispatch-table trace-table"><thead><tr>'
        '<th scope="col">Agent</th><th scope="col">Round</th><th scope="col">Duration</th>'
        '<th scope="col">Lane</th><th scope="col">Summary</th></tr></thead><tbody>'
        + "".join(body)
        + "</tbody></table></div>"
    )


def active_route_segments(plan: Any) -> set[str]:
    return {
        segment
        for assignment in plan_to_dict(plan).get("assignments", [])
        for segment in (assignment.model_dump() if hasattr(assignment, "model_dump") else assignment).get("route", [])
    }


def plan_signal_key(plan: Any) -> str:
    """Stable key used to animate only when the selected plan changes."""
    data = plan_to_dict(plan)
    signal = {
        "version": data.get("version"),
        "assignments": [
            {
                "community_id": item.get("community_id"),
                "resource": item.get("resource"),
                "quantity": item.get("quantity"),
                "vehicle_id": item.get("vehicle_id"),
                "route": item.get("route", []),
            }
            for raw in data.get("assignments", [])
            for item in [raw.model_dump() if hasattr(raw, "model_dump") else raw]
        ],
    }
    return json.dumps(signal, sort_keys=True, separators=(",", ":"))


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @font-face {
            font-family: "Dispatch Condensed";
            src: url("/app/static/fonts/BarlowCondensed-Medium.ttf") format("truetype");
            font-style: normal; font-weight: 500; font-display: swap;
        }
        @font-face {
            font-family: "Dispatch Condensed";
            src: url("/app/static/fonts/BarlowCondensed-Bold.ttf") format("truetype");
            font-style: normal; font-weight: 700; font-display: swap;
        }
        :root { color-scheme: dark; }
        html { scrollbar-color: #5d6769 #0d0f0f; }
        ::selection { background: #ffb400; color: #0d0f0f; }
        [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: #0d0f0f; color: #f2f2f2; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stAppDeployButton"], [data-testid="stStatusWidget"], [data-testid="stToolbarActions"], #MainMenu {
            display: none !important;
        }
        [data-testid="stSidebar"] { background: #121617; border-right: 1px solid #41494b; }
        [data-testid="stSidebar"] * { color: #f2f2f2; }
        .block-container { max-width: 1500px; padding-top: 1.5rem; padding-bottom: 4rem; }
        h1, h2, h3, .dispatch-label, .dispatch-table th, .mode-chip {
            font-family: "Dispatch Condensed", sans-serif;
            letter-spacing: .075em;
            text-transform: uppercase;
        }
        h1, h2, h3 { color: #f2f2f2 !important; }
        p, li, label, .stMarkdown { color: #cbd0d1; }
        a { color: #ffb400 !important; text-underline-offset: 3px; }
        .resq-header { border: 1px solid #596265; background: #101415; padding: 18px 22px;
            display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 10px; }
        .resq-brand { color: #f2f2f2; font: 700 1.8rem/1 "Dispatch Condensed", sans-serif;
            letter-spacing: .12em; }
        .resq-meta { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
        .mode-chip { border: 1px solid #697477; color: #d7dbdc; padding: 7px 10px; font-size: .78rem; }
        .mode-chip strong { color: #ffb400; font-variant-numeric: tabular-nums; }
        .event-strip { display: flex; justify-content: space-between; gap: 16px; padding: 10px 14px;
            background: #202729; border: 1px solid #596265; color: #f2f2f2; margin-bottom: 18px;
            font-family: "Dispatch Condensed", sans-serif; letter-spacing: .055em; }
        .event-strip.escalated { background: #3a1717; border-color: #d32f2f; }
        .event-strip b { color: #ffb400; }
        .section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 14px;
            border-bottom: 1px solid #596265; margin: 20px 0 12px; padding-bottom: 8px; }
        .section-head h2 { margin: 0; font-size: 1.15rem; }
        .section-head span { color: #9ba4a6; font-size: .82rem; }
        .map-frame { border: 1px solid #596265; background: #101516; padding: 9px; }
        .map-frame svg { display: block; width: 100%; height: auto; min-height: 310px; }
        .map-frame text { fill: #d9dddd; font: 11px "Dispatch Condensed", sans-serif;
            paint-order: stroke; stroke: #101516; stroke-width: 3px; }
        .map-frame circle { fill: #f2f2f2; stroke: #101516; stroke-width: 2px; }
        .map-frame .node-label { fill: #aeb6b8; font-size: 9px; }
        .map-legend { display: flex; gap: 18px; flex-wrap: wrap; border-top: 1px solid #3f4749; padding: 10px 5px 2px;
            color: #cbd0d1; font-size: .82rem; }
        .map-legend span { display: inline-flex; align-items: center; gap: 7px; }
        .map-legend i { display: inline-block; width: 28px; height: 4px; background: #70c1a5; }
        .map-legend i.flooded { background: repeating-linear-gradient(90deg,#ffb400 0 8px,transparent 8px 13px); }
        .map-legend i.blocked { background: repeating-linear-gradient(90deg,#d32f2f 0 3px,transparent 3px 7px); }
        .decision-panel { border: 1px solid #596265; background: #121617; padding: 18px; min-height: 100%; }
        .decision-state { font: 700 1.7rem/1.1 "Dispatch Condensed", sans-serif;
            letter-spacing: .06em; text-transform: uppercase; color: #f2f2f2; margin-bottom: 16px; }
        .decision-state em { color: #70c1a5; font-style: normal; }
        .decision-state.danger em { color: #ef5b55; }
        .metric-line { display: grid; grid-template-columns: 1fr auto; padding: 10px 0; border-top: 1px solid #394143; }
        .metric-line span { color: #9fa8aa; }
        .metric-line strong { color: #f2f2f2; font-variant-numeric: tabular-nums; }
        .escalation-banner { background: #3a1717; border: 1px solid #d32f2f; padding: 16px 18px; margin: 14px 0 18px; }
        .escalation-banner h2 { color: #ff8b86 !important; font-size: 1rem; margin: 0 0 7px; }
        .escalation-banner p { margin: 5px 0; color: #ffe0de; }
        .table-shell { position: relative; }
        .scroll-hint { display: none; color: #ffb400; border: 1px solid #596265; border-bottom: 0;
            padding: 8px 10px; font-size: .78rem; letter-spacing: .02em; }
        .table-scroll { border: 1px solid #596265; overflow: auto; max-height: 540px; background: #101415;
            scrollbar-color: #ffb400 #171c1d; }
        .trace-scroll { max-height: 460px; }
        .dispatch-table { width: 100%; min-width: 1040px; border-collapse: collapse; color: #f2f2f2; }
        .dispatch-table th { position: sticky; top: 0; z-index: 1; background: #252c2e; color: #ffb400;
            padding: 10px 12px; text-align: left; font-size: .75rem; border-bottom: 1px solid #6f7a7d; }
        .dispatch-table td { padding: 11px 12px; border-bottom: 1px solid #333a3c; vertical-align: top; }
        .dispatch-table tbody tr { background: #111617; }
        .dispatch-table.signal tbody tr { animation: row-signal .5s cubic-bezier(.2,.8,.2,1) both;
            animation-delay: calc(var(--row-index, 0) * 35ms); }
        .dispatch-table tbody tr:nth-child(even) { background: #151b1c; }
        .dispatch-table tbody tr:hover { background: #20292b; }
        .dispatch-table .priority, .dispatch-table .quantity { color: #ffb400; font-weight: 800;
            font-variant-numeric: tabular-nums; }
        .dispatch-table .route { white-space: nowrap; color: #d7dbdc; }
        .dispatch-table .reason { min-width: 280px; color: #adb5b7; }
        .trace-table { min-width: 820px; }
        .empty-state { border: 1px dashed #596265; padding: 28px; color: #aeb6b8; text-align: center; }
        [data-testid="stButton"] button { border-radius: 2px; border: 1px solid #ffb400; background: #151a1b;
            color: #ffb400; min-height: 42px; font-family: "Dispatch Condensed", sans-serif;
            letter-spacing: .06em; text-transform: uppercase; font-weight: 800; }
        [data-testid="stButton"] button:hover { background: #ffb400; color: #0d0f0f; border-color: #ffb400; }
        [data-testid="stButton"] button:focus-visible, input:focus-visible, [role="combobox"]:focus-visible {
            outline: 3px solid #f2f2f2 !important; outline-offset: 2px; }
        [data-testid="stSelectbox"] > div > div, [data-testid="stRadio"] { color: #f2f2f2; }
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            background: #171c1d !important; border-color: #667174 !important; border-radius: 2px;
        }
        [data-testid="stSelectbox"] div[data-baseweb="select"] * { color: #f2f2f2 !important; }
        [data-testid="stSidebar"] [role="combobox"] { background: #171c1d !important; color: #f2f2f2 !important; }
        [data-baseweb="popover"] [role="listbox"] { background: #171c1d !important; }
        [data-baseweb="popover"] [role="option"] { color: #f2f2f2 !important; }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #596265; }
        [data-testid="stTabs"] button { color: #abb3b5; border-radius: 0; }
        [data-testid="stTabs"] button[aria-selected="true"] { color: #ffb400; border-bottom-color: #ffb400; }
        @keyframes row-signal { from { background: #4b3905; filter: brightness(1.18); } to { filter: none; } }
        @media (prefers-reduced-motion: reduce) { .dispatch-table.signal tbody tr { animation: none; } }
        @media (max-width: 760px) {
            .block-container { padding: .75rem 1rem 3rem; }
            .resq-header { align-items: flex-start; flex-direction: column; padding: 12px 14px; gap: 10px; }
            .resq-brand { font-size: 1.5rem; }
            .resq-meta { justify-content: flex-start; gap: 5px; }
            .mode-chip { padding: 5px 7px; font-size: .7rem; }
            .event-strip { display: block; padding: 9px 12px; margin-bottom: 8px; font-size: .84rem; }
            .event-strip span:last-child { display: none; }
            .section-head { margin: 12px 0 8px; padding-bottom: 6px; }
            .decision-panel { padding: 13px 15px; }
            .decision-state { font-size: 1.45rem; margin-bottom: 10px; }
            .metric-line { padding: 7px 0; }
            .map-frame svg { min-height: 0; }
            [data-testid="stHorizontalBlock"]:has(.map-frame) { flex-direction: column-reverse; }
            .scroll-hint { display: block; }
            .dispatch-table { min-width: 930px; }
            .dispatch-table th:nth-child(1), .dispatch-table td:nth-child(1) {
                position: sticky; left: 0; width: 76px; min-width: 76px; z-index: 2;
            }
            .dispatch-table th:nth-child(2), .dispatch-table td:nth-child(2) {
                position: sticky; left: 76px; width: 108px; min-width: 108px; z-index: 2;
                box-shadow: 1px 0 #596265;
            }
            .dispatch-table th:nth-child(-n+2) { z-index: 4; background: #252c2e; }
            .dispatch-table tbody td:nth-child(-n+2) { background: #111617; }
            .dispatch-table tbody tr:nth-child(even) td:nth-child(-n+2) { background: #151b1c; }
            .dispatch-table tbody tr:hover td:nth-child(-n+2) { background: #20292b; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _run_live(question: str, event: dict[str, str] | None = None) -> None:
    """Execute one live workflow and preserve the last good result on error."""
    try:
        from resq import world
        from resq.run import execute

        with st.spinner("Agents are reconciling evidence, planning, and reviewing..."):
            result = execute(question, event)
            map_state = world.get_state()
        st.session_state.live_result = result
        st.session_state.live_map_state = map_state
        st.session_state.live_error = ""
    except Exception as exc:  # Streamlit must show a recoverable service failure.
        st.session_state.live_error = f"Live run failed: {exc}"


def _initial_live_map() -> dict[str, Any]:
    if st.session_state.get("live_map_state"):
        return st.session_state.live_map_state
    try:
        from resq import scenario, world

        scenario.bootstrap()
        state = world.get_state()
        st.session_state.live_map_state = state
        return state
    except Exception as exc:
        st.session_state.live_error = f"Live services are not ready: {exc}"
        return {"road_nodes": {}, "road_segments": {}}


def _render_header(mode: str, plan: dict[str, Any], request_type: str) -> None:
    version = plan.get("version", "—")
    confidence = plan.get("confidence")
    confidence_text = f"{float(confidence):.0%}" if confidence is not None else "—"
    st.markdown(
        f"""
        <div class="resq-header">
          <div class="resq-brand">RESQ AI</div>
          <div class="resq-meta">
            <span class="mode-chip">Mode <strong>{html.escape(mode.upper())}</strong></span>
            <span class="mode-chip">Plan <strong>V{html.escape(str(version))}</strong></span>
            <span class="mode-chip">Confidence <strong>{html.escape(confidence_text)}</strong></span>
            <span class="mode-chip">Request <strong>{html.escape((request_type or "ready").upper())}</strong></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_decision(plan: dict[str, Any], result: dict[str, Any]) -> None:
    assignments = plan.get("assignments", [])
    communities = {item.get("community_id") for item in assignments if isinstance(item, dict)}
    unserved = plan.get("unserved", [])
    escalated = bool(result.get("escalated") or plan.get("escalated"))
    state_class = "danger" if escalated else ""
    state_text = "Human decision required" if escalated else "Plan ready for dispatch"
    state_value = "ESCALATED" if escalated else "ACTIVE"
    st.markdown(
        f"""
        <div class="decision-panel">
          <div class="decision-state {state_class}">{html.escape(state_text)}<br><em>{state_value}</em></div>
          <div class="metric-line"><span>Assignments</span><strong>{len(assignments)}</strong></div>
          <div class="metric-line"><span>Communities served</span><strong>{len(communities)}</strong></div>
          <div class="metric-line"><span>Unserved</span><strong>{len(unserved)}</strong></div>
          <div class="metric-line"><span>Agent steps</span><strong>{len(result.get("trace", []))}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_escalation(plan: dict[str, Any], escalated: bool) -> None:
    if not escalated:
        return
    reasons = escalation_reasons(plan)
    if not reasons:
        reasons = ["Escalation was set, but no P8.3 reason was returned. Review the critic trace before dispatch."]
    paragraphs = "".join(f"<p>{html.escape(reason)}</p>" for reason in reasons)
    st.markdown(
        '<div class="escalation-banner" role="alert"><h2>Human decision required</h2>'
        + paragraphs
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_live_actions(map_state: dict[str, Any]) -> None:
    st.markdown('<div class="section-head"><h2>Coordinator actions</h2><span>Writes authoritative events</span></div>', unsafe_allow_html=True)
    plan_col, why_col = st.columns(2)
    with plan_col:
        if st.button("Plan now", use_container_width=True):
            _run_live("How should we distribute aid right now?")
            st.rerun()
    with why_col:
        if st.button("Why did the plan change?", use_container_width=True):
            _run_live("Why did the plan change?")
            st.rerun()

    segment_ids = sorted(map_state.get("road_segments", {}))
    segment_col, block_col = st.columns([1.35, 0.65], vertical_alignment="bottom")
    with segment_col:
        selected = st.selectbox("Road segment", segment_ids, index=segment_ids.index("T6") if "T6" in segment_ids else 0)
    with block_col:
        if st.button("Block segment", use_container_width=True, disabled=not segment_ids):
            _run_live("", {"type": "segment_blocked", "id": selected, "source": "coordinator"})
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="RESQ AI · Flood response", page_icon="R", layout="wide")
    _inject_styles()

    with st.sidebar:
        st.markdown("## Operations source")
        mode = st.radio("Data mode", ("Example", "Live"), help="Example mode uses committed outputs. Live mode runs the agent graph.")
        if mode == "Example":
            example_key = st.selectbox(
                "Plan version",
                options=list(EXAMPLE_RUNS),
                format_func=lambda key: EXAMPLE_RUNS[key]["label"],
            )
            st.caption("Offline · committed synthetic scenario")
        else:
            st.caption("Connected · uses the configured data, model, and World Model services")
        st.markdown("---")
        st.caption("Synthetic municipal scenario. Protocol decisions remain subject to human review.")

    if mode == "Example":
        result, map_state = load_example_run(example_key)
    else:
        result = st.session_state.get(
            "live_result",
            {"run_id": "", "request_type": "ready", "plan": None, "report": "", "trace": [], "escalated": False, "reviews": []},
        )
        map_state = _initial_live_map()

    plan = plan_to_dict(result.get("plan"))
    _render_header(mode, plan, str(result.get("request_type") or "ready"))

    if mode == "Example":
        label = "Baseline plan · no coordinator event" if example_key == "baseline" else "Coordinator event · segment T6 blocked"
    else:
        label = "Live system · waiting for a coordinator action" if not plan else "Live system · latest agent result"
    strip_class = "escalated" if result.get("escalated") else ""
    st.markdown(
        f'<div class="event-strip {strip_class}"><span><b>INCIDENT STATE</b> · {html.escape(label)}</span>'
        f'<span>Run {html.escape(str(result.get("run_id") or "not started"))}</span></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.get("live_error") and mode == "Live":
        st.error(st.session_state.live_error)

    if not plan:
        if mode == "Live":
            _render_live_actions(map_state)
        st.info("No live plan has been generated yet. Use Plan now to start the multi-agent workflow.")
        st.markdown('<div class="section-head"><h2>Road network</h2><span>Current verified state</span></div>', unsafe_allow_html=True)
        st.markdown(build_map_svg(map_state), unsafe_allow_html=True)
        return

    _render_escalation(plan, bool(result.get("escalated") or plan.get("escalated")))

    map_col, decision_col = st.columns([1.35, 0.65], gap="medium")
    with map_col:
        st.markdown('<div class="section-head"><h2>Road network</h2><span>Active routes are heavier</span></div>', unsafe_allow_html=True)
        st.markdown(build_map_svg(map_state, active_route_segments(plan)), unsafe_allow_html=True)
    with decision_col:
        st.markdown('<div class="section-head"><h2>Current decision</h2><span>One delivery round</span></div>', unsafe_allow_html=True)
        _render_decision(plan, result)
        if mode == "Live":
            _render_live_actions(map_state)

    st.markdown('<div class="section-head"><h2>Dispatch assignments</h2><span>Ordered by planner priority</span></div>', unsafe_allow_html=True)
    signal_key = plan_signal_key(plan)
    previous_signal_key = st.session_state.get("rendered_plan_signal_key")
    animate_assignments = previous_signal_key is not None and previous_signal_key != signal_key
    st.session_state.rendered_plan_signal_key = signal_key
    st.markdown(render_assignment_table(plan, animate=animate_assignments), unsafe_allow_html=True)

    report_tab, trace_tab, risks_tab = st.tabs(("Coordinator brief", "Agent trace", "Risks and changes"))
    with report_tab:
        report = result.get("report") or "No coordinator brief was returned for this run."
        st.markdown(report)
    with trace_tab:
        st.markdown(render_trace_table(result.get("trace", [])), unsafe_allow_html=True)
    with risks_tab:
        st.markdown("### Risks")
        risks = plan.get("risks", [])
        if risks:
            for risk in risks:
                st.markdown(f"- {risk}")
        else:
            st.info("No plan risks were returned.")
        st.markdown("### Changes from the previous plan")
        changes = plan.get("changes_vs_previous", [])
        if changes:
            for change in changes:
                st.markdown(f"- {change}")
        else:
            st.caption("This is the baseline plan or no changes were returned.")


if __name__ == "__main__":
    main()
