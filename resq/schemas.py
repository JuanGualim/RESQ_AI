"""Shared data contracts (AGENTS.md section 6). Changing a field = tell the team + log it in section 10."""
from __future__ import annotations

import operator
from typing import Annotated, Literal

from pydantic import BaseModel, Field

RequestType = Literal["situation", "plan", "event", "why"]


class Assignment(BaseModel):
    community_id: str
    origin_id: str  # warehouse id
    resource: str
    quantity: int = Field(gt=0)
    vehicle_id: str
    route: list[str] = Field(default_factory=list)  # road segment ids, filled by best_route
    priority: int = Field(ge=1)
    reason: str
    evidence: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    version: int = 1
    assignments: list[Assignment] = Field(default_factory=list)
    unserved: list[str] = Field(default_factory=list)  # community ids, with the reason in risks
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    escalated: bool = False
    changes_vs_previous: list[str] = Field(default_factory=list)


class Route(BaseModel):
    origin: str  # road node
    destination: str  # road node
    nodes: list[str]
    segments: list[str]
    distance_km: float


class Event(BaseModel):
    """A coordinator event entered in the UI or the CLI, e.g. blocking a road segment."""

    type: Literal["segment_blocked", "segment_reopened"]
    id: str
    source: str = "coordinator"
    ts: str | None = None
    detail: str = ""


class CriticReview(BaseModel):
    round: int
    approved: bool
    violations: list[str] = Field(default_factory=list)  # hard rules from validators.validate_plan
    feedback: list[str] = Field(default_factory=list)  # LLM review of reasons and evidence


class ResqState(BaseModel):
    """LangGraph state. Domain state (roads, risks, plans) lives in the World Model."""

    run_id: str
    question: str = ""
    event: Event | None = None
    request_type: RequestType | None = None
    as_of: str = ""  # scenario time of this run
    situation: list[str] = Field(default_factory=list)  # Risk Analyst summary
    plan: Plan | None = None
    previous_plan: Plan | None = None
    pack_shortfalls: list[str] = Field(default_factory=list)  # what packing could not carry
    critic_round: int = 0
    reviews: Annotated[list[CriticReview], operator.add] = Field(default_factory=list)
    approved: bool = False
    escalated: bool = False
    report: str = ""
    trace: Annotated[list[dict], operator.add] = Field(default_factory=list)
