# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is a municipal emergency coordinator working during a flood. They need to understand the current situation, review an aid distribution plan, intervene when road conditions change, and explain why the plan changed.

## Product Purpose

RESQ AI turns contradictory field reports, road conditions, supply constraints, and community needs into a versioned flood-aid distribution plan. Success means the coordinator can act on a plan, see its evidence and limitations, and trigger a transparent re-plan when reality changes.

## Positioning

RESQ AI combines deterministic protocol enforcement and routing with a multi-agent critique loop and a shared, versioned World Model. The interface exposes that reasoning trace instead of presenting a plan as an unexplained model answer.

## Operating Context

The coordinator uses a Streamlit dashboard during a fictional Hurricane Eta scenario. The core workflow is to review a baseline plan, inspect assignments and road status, block a road segment, receive a revised plan, and ask what changed and why. Judges may also run the interface offline from committed example outputs.

## Capabilities and Constraints

- The dashboard must work in an offline example mode and a live mode backed by `resq.run.execute()`.
- Scenario data comes only from Zetaris, except when `SAMPLE_MODE=true` uses the committed sample data.
- All model calls go through `resq/llm.py`; UI code never calls a model provider directly.
- Plans expose assignments, risks, escalation state, confidence, changes, and an agent trace.
- Coordinator road events are authoritative and must use the existing `segment_blocked` event contract.
- All repository and demo-facing copy is English.
- The interface must not hardcode conclusions that should come from scenario data or agent output.

## Evidence on Hand

- Synthetic scenario tables: `data/sample/`
- Scenario and contradiction documentation: `data/README.md`
- Protocol rules: `docs/protocol.md`
- Baseline, blocked-road, and explanation examples: `output_examples/`
- Structured plan, trace, and execution contracts: `resq/schemas.py` and `resq/run.py`

The repository has no real users, customer claims, operational deployment evidence, or production performance claims; future work must not fabricate them.

## Product Principles

- Make operational state and escalation visible at a glance.
- Keep evidence and agent reasoning inspectable without obscuring the current decision.
- Treat coordinator events as explicit, consequential actions.
- Prefer deterministic calculations for routes, capacities, inventory, and hard rules.
- Preserve a usable offline path for judges and development without services.

## Accessibility & Inclusion

Do not rely on color alone for road status or escalation. Controls, tables, trace entries, and status labels need readable text, keyboard-compatible native interactions, and sufficient contrast.
