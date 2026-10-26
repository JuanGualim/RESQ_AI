from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.streamlit_app import (
    active_route_segments,
    assignment_rows,
    build_map_svg,
    escalation_reasons,
    load_example_run,
    plan_signal_key,
    render_assignment_table,
    trace_rows,
)


APP_PATH = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def test_live_mode_can_import_the_agent_package():
    # Streamlit runs the app with app/ as the script directory, so without the repo
    # root on sys.path live mode failed with "Live services are not ready:
    # No module named 'resq'" while example mode kept working.
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    assert not app.exception
    import importlib

    source = APP_PATH.read_text(encoding="utf-8")
    assert "sys.path.insert" in source, "the app must put the repo root on sys.path"
    assert importlib.import_module("resq.run").execute


def test_example_versions_load_expected_state():
    baseline, baseline_map = load_example_run("baseline")
    blocked, blocked_map = load_example_run("blocked")

    assert baseline["plan"]["version"] == 1
    assert blocked["plan"]["version"] == 2
    assert baseline_map["road_segments"]["T6"]["status"] == "open"
    assert blocked_map["road_segments"]["T6"]["status"] == "blocked"


def test_escalation_banner_uses_exact_p8_3_risks():
    result, _ = load_example_run("blocked")
    reasons = escalation_reasons(result["plan"])
    assert len(reasons) == 1
    assert reasons[0].startswith("P8.3: P5.2 infeasible")


def test_assignment_and_trace_rows_keep_required_fields():
    result, _ = load_example_run("baseline")
    assignment = assignment_rows(result["plan"])[0]
    trace = trace_rows(result["trace"])[0]

    assert {"priority", "community", "resource", "quantity", "vehicle", "route", "reason"} <= assignment.keys()
    assert {"agent", "round", "duration", "summary"} <= trace.keys()


def test_map_svg_exposes_status_with_text_and_line_style():
    result, map_state = load_example_run("blocked")
    svg = build_map_svg(map_state, active_route_segments(result["plan"]))

    assert "T6: Blocked" in svg
    assert "Flooded / limited" in svg
    assert "Blocked / closed" in svg
    assert 'stroke-dasharray="2 4"' in svg


def test_assignment_table_escapes_agent_content():
    plan = {
        "assignments": [
            {
                "priority": 1,
                "community_id": "C<script>",
                "resource": "water_20l",
                "quantity": 1,
                "vehicle_id": "V1",
                "route": ["T1"],
                "reason": "<b>unsafe</b>",
            }
        ]
    }
    table = render_assignment_table(plan)
    assert "<script>" not in table
    assert "&lt;script&gt;" in table
    assert "&lt;b&gt;unsafe&lt;/b&gt;" in table


def test_assignment_signal_only_appears_when_requested():
    result, _ = load_example_run("baseline")
    assert 'dispatch-table signal' not in render_assignment_table(result["plan"])
    assert 'dispatch-table signal' in render_assignment_table(result["plan"], animate=True)
    assert plan_signal_key(result["plan"]) == plan_signal_key(result["plan"])


def test_streamlit_modes_render_without_exceptions():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    assert not app.exception
    assert app.radio[0].value == "Example"

    app.selectbox[0].select("blocked").run(timeout=20)
    assert not app.exception
    assert any("Human decision required" in str(markdown.value) for markdown in app.markdown)

    app.radio[0].set_value("Live").run(timeout=20)
    assert not app.exception
    assert [button.label for button in app.button] == ["Plan now", "Why did the plan change?", "Block segment"]
