"""The RESQ AI agent graph (LangGraph).

    intake ─┬─ why ───────────────────────────────────────────────► explainer
            └─ plan/event/situation ─► reconciler ─► risk_analyst ─┬─ situation ─► explainer
                                                                   └─► planner ⇄ critic (max 3 rounds)
                                                                                 └─ approved/escalated ─► explainer
"""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from resq.agents.critic import node_critic, route_after_critic
from resq.agents.explainer import node_explainer
from resq.agents.intake import node_intake
from resq.agents.planner import node_planner
from resq.agents.reconciler import node_reconciler
from resq.agents.risk_analyst import node_risk_analyst
from resq.schemas import ResqState


def _after_intake(state: ResqState) -> str:
    return "explainer" if state.request_type == "why" else "reconciler"


def _after_risk(state: ResqState) -> str:
    return "explainer" if state.request_type == "situation" else "planner"


@lru_cache(maxsize=1)
def build_graph():
    graph = StateGraph(ResqState)
    graph.add_node("intake", node_intake)
    graph.add_node("reconciler", node_reconciler)
    graph.add_node("risk_analyst", node_risk_analyst)
    graph.add_node("planner", node_planner)
    graph.add_node("critic", node_critic)
    graph.add_node("explainer", node_explainer)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", _after_intake, {"explainer": "explainer", "reconciler": "reconciler"})
    graph.add_edge("reconciler", "risk_analyst")
    graph.add_conditional_edges("risk_analyst", _after_risk, {"explainer": "explainer", "planner": "planner"})
    graph.add_edge("planner", "critic")
    graph.add_conditional_edges("critic", route_after_critic, {"planner": "planner", "explainer": "explainer"})
    graph.add_edge("explainer", END)
    return graph.compile()
