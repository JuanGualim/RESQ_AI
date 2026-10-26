"""Agents with the model replaced by deterministic fakes (no network)."""
import pytest

from resq import llm, scenario, world
from resq.agents import critic, explainer, intake, planner, reconciler, risk_analyst
from resq.agents.critic import route_after_critic, stock_cuts
from resq.schemas import Assignment, Plan, ResqState
from resq.tools.packing import pack
from resq.tools.validators import critical_minimum_gaps, validate_plan


def fail(*args, **kwargs):
    raise llm.LLMError("model disabled in tests")


@pytest.fixture
def no_model(monkeypatch):
    monkeypatch.setattr(llm, "chat", fail)
    monkeypatch.setattr(llm, "chat_json", fail)


@pytest.fixture
def assessed(state, no_model):
    """World with reconciler and risk analyst applied (code paths only)."""
    run = ResqState(run_id="test", as_of=scenario.now())
    reconciler.node_reconciler(run)
    risk_analyst.node_risk_analyst(run)
    return world.get_state()


@pytest.mark.parametrize("question, has_event, expected", [
    ("How should we distribute aid right now?", False, "plan"),
    ("Why did the plan change?", False, "why"),
    ("¿Por qué cambió el plan?", False, "why"),
    ("What is the current situation?", False, "situation"),
    ("anything", True, "event"),
])
def test_intake_classify(question, has_event, expected):
    assert intake.classify(question, has_event) == expected


def test_reconciler_scores_seeded_contradictions(state):
    objects = {o["object_id"]: o for o in reconciler.score_reports(reconciler.load_reports())}
    assert objects["T7"]["computed_status"] == "flooded" and objects["T7"]["computed_confidence"] >= 0.65
    assert objects["T11"]["computed_status"] == "uncertain"
    assert objects["T14"]["computed_status"] == "damaged"
    assert objects["T3"]["computed_status"] == "open" and not objects["T3"]["contested"]
    assert objects["T18"]["computed_status"] == "closed"
    assert objects["C05"]["computed_confidence"] < 0.65  # lone social media post


def test_reconciler_rejects_invented_status(state):
    obj = next(o for o in reconciler.score_reports(reconciler.load_reports()) if o["object_id"] == "T7")
    assert reconciler._accept(obj, {"status": "teleported", "confidence": 1})["decided_by"] == "code"
    accepted = reconciler._accept(obj, {"status": "open", "confidence": 0.7, "evidence": ["R001", "R999"]})
    assert accepted["status"] == "open" and accepted["evidence"] == ["R001"]


def test_reconciler_writes_facts_to_world(assessed):
    assert assessed["road_segments"]["T7"]["status"] == "flooded"
    assert assessed["road_segments"]["T7"]["status_evidence"]
    assert assessed["shelters"]["S2"]["status"] == "full"


def test_risk_levels_and_needs(assessed):
    c07 = assessed["communities"]["C07"]
    assert c07["risk_level"] == "critical"
    assert c07["needs"]["water_20l"] == c07["needs"]["food_kit"] > 0
    low = [c for c in assessed["communities"].values() if c["risk_level"] == "low"]
    assert all(not c["needs"] for c in low)


def test_rain_last_24h_uses_eta_snapshot(state):
    assert risk_analyst.rain_last_24h("2020-11-05T10:00:00") == pytest.approx(145.6, abs=0.5)


def test_stable_community_gets_half_the_need():
    community = {"population": 1000, "pct_elderly": 5, "reported_status": None}
    full = risk_analyst.needs(community, "critical")
    half = risk_analyst.needs(community | {"reported_status": "stable"}, "critical")
    assert half["water_20l"] == pytest.approx(full["water_20l"] / 2, abs=1)


def test_packing_respects_capacity_trips_and_stock(assessed):
    result = pack([{"community_id": "C07", "resource": "water_20l", "quantity": 2000, "priority": 1}], assessed)
    plan = Plan(assignments=result.assignments)
    assert [v for v in validate_plan(plan, assessed) if not v.startswith("P5")] == []  # only C07 is served here
    delivered = sum(a.quantity for a in result.assignments)
    assert delivered <= 896 and result.shortfalls


def test_packing_unreachable_is_a_shortfall(assessed):
    for segment_id in ("T1", "T2", "T3"):
        assessed["road_segments"][segment_id]["status"] = "blocked"
    result = pack([{"community_id": "C07", "resource": "water_20l", "quantity": 10, "priority": 1}], assessed)
    assert not result.assignments and "no vehicle can reach it" in result.shortfalls[0]


def test_planner_tiers_give_every_critical_its_minimum_first(assessed):
    decision = {"priorities": [{"community_id": cid, "rank": 1, "tier": "full", "reason": "test", "evidence": ["P5"]}
                               for cid, c in assessed["communities"].items() if c["risk_level"] != "low"]}
    allocations, _ = planner.clean_allocations(decision, assessed)
    critical = [cid for cid, c in assessed["communities"].items() if c["risk_level"] == "critical"]
    first = allocations[: len(critical) * 3]  # water, food, medical minimums come first
    assert {a["community_id"] for a in first} == set(critical)


def test_planner_plan_passes_hard_rules(assessed):
    decision = {"priorities": [{"community_id": cid, "rank": 1, "tier": "minimum" if c["risk_level"] == "critical" else "none",
                                "reason": "test", "evidence": ["P5.2"]}
                               for cid, c in assessed["communities"].items() if c["risk_level"] != "low"], "confidence": 0.8}
    plan, _ = planner.to_plan(decision, assessed, version=1)
    assert plan.assignments and validate_plan(plan, assessed) == []


def test_planner_sees_the_coordinator_events_that_caused_the_replan(assessed, no_model):
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator",
                       "ts": scenario.next_coordinator_ts()})
    world.apply_event({"type": "segment_reopened", "id": "T6", "source": "coordinator",
                       "ts": scenario.next_coordinator_ts()})
    run = ResqState(run_id="test", as_of=scenario.now(), previous_plan=Plan(version=2))
    context = planner.build_context(world.get_state(), run)
    events = [e["type"] for e in context["new_events"]]
    assert "segment_blocked" in events and "segment_reopened" in events


def test_reopening_a_segment_restores_its_status(assessed, no_model):
    # The re-plan after a reopening is only comparable to the baseline if the world
    # really went back: the coordinator's reopening must win over the block.
    assert world.get_state()["road_segments"]["T6"]["status"] == "open"
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator",
                       "ts": scenario.next_coordinator_ts()})
    assert world.get_state()["road_segments"]["T6"]["status"] == "blocked"
    world.apply_event({"type": "segment_reopened", "id": "T6", "source": "coordinator",
                       "ts": scenario.next_coordinator_ts()})
    assert world.get_state()["road_segments"]["T6"]["status"] == "open"


def test_blocking_t6_makes_the_critical_minimum_infeasible(assessed, no_model):
    assert critical_minimum_gaps(assessed) == []
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": scenario.next_coordinator_ts()})
    risk_analyst.node_risk_analyst(ResqState(run_id="test", as_of=scenario.now()))
    gaps = critical_minimum_gaps(world.get_state())
    assert any("fording vehicles carry 13,800 kg" in gap for gap in gaps)


def test_review_payload_carries_reachability(assessed):
    # The phase 3 battery showed 9-10 false blocks per 30 turns on the blocking
    # scenarios: the Critic could not see that a community had become ford_only and
    # read its lower coverage as a ranking mistake.
    from resq.agents.common import plan_by_community
    plan = Plan(assignments=[Assignment(community_id="C07", origin_id="W1", resource="water_20l", quantity=10,
                                        vehicle_id="V1", route=[], priority=1, reason="x", evidence=[])])
    summary = plan_by_community(plan, assessed)
    assert "reachability" in summary["C07"]
    assert summary["C07"]["reachability"] in ("all", "ford_only", "none")
    assert "reachability" in critic.SYSTEM_PROMPT and "ford_only" in critic.SYSTEM_PROMPT


def test_critic_tells_stock_cuts_apart_from_other_risks():
    # Coverage lost to an empty warehouse is scarcity, not a ranking mistake, so the
    # reason review gets it as its own field instead of buried in the risk list.
    plan = Plan(risks=["P6.2: C07 water_20l: stock ran out, 10 of 50 units",
                       "P1.2: T6 blocked by the coordinator",
                       "P6.2: C12 food_kit: stock ran out, 0 of 30 units"])
    assert stock_cuts(plan) == ["P6.2: C07 water_20l: stock ran out, 10 of 50 units",
                                "P6.2: C12 food_kit: stock ran out, 0 of 30 units"]
    assert stock_cuts(Plan(risks=["P1.2: T6 blocked by the coordinator"])) == []


def test_route_after_critic():
    plan = Plan()
    assert route_after_critic(ResqState(run_id="t", approved=True, plan=plan)) == "explainer"
    assert route_after_critic(ResqState(run_id="t", approved=False, plan=plan, critic_round=1)) == "planner"
    assert route_after_critic(ResqState(run_id="t", approved=False, plan=plan, critic_round=3)) == "explainer"
    assert route_after_critic(ResqState(run_id="t", approved=False, plan=None, critic_round=1)) == "explainer"


def test_diff_plans():
    a = dict(community_id="C04", origin_id="W1", resource="water_20l", vehicle_id="V1", priority=1, reason="r")
    before = Plan(version=1, assignments=[Assignment(quantity=50, route=["T3", "T6", "T8"], **a)])
    after = Plan(version=2, assignments=[Assignment(quantity=30, route=["T3", "T7"], **(a | {"vehicle_id": "V2"}))], unserved=["C07"])
    changes = explainer.diff_plans(before, after)
    assert "C04 water_20l: 50 -> 30 units; V1 via T3-T6-T8 -> V2 via T3-T7" in changes
    assert "C07: now unserved" in changes
    assert explainer.diff_plans(None, after) == []


def test_change_events_follow_observation_time(state):
    world.save_plan({"version": 1, "assignments": []}, ts="2020-11-05T10:00:00")
    world.apply_event({"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": "2020-11-05T10:05:00"})
    # written later but observed earlier: must not appear as "T6 reopened"
    world.apply_event({"type": "segment_status_verified", "id": "T6", "status": "open", "source": "agent", "ts": "2020-11-05T09:45:00"})
    events = explainer.events_since_previous_plan(Plan(version=1))
    assert [(e["id"], e["status"]) for e in events] == [("T6", "blocked")]
