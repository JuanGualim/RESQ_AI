# RESQ AI architecture

How RESQ AI reasons, where each sponsor technology does real work, and how to verify every claim in this document from the repo. For setup see [`TEAM_SETUP.md`](TEAM_SETUP.md); for the domain rules cited below (`P1`–`P8`) see [`protocol.md`](protocol.md).

## 1. The decision and why it needs a reasoning architecture

A municipal emergency coordinator must decide, during a flood, which communities get which supplies, from which warehouse, by which vehicle and road. Three things make this hard:

- **The facts are contested.** Field reports from official bulletins, brigades and social media contradict each other (e.g. T7: "open" in the bulletin, "flooded 60 cm" from two brigades).
- **Resources are scarce.** Stock and vehicle capacity do not cover every need, so the plan is a prioritization, not a lookup.
- **Reality changes.** A road gets blocked and the plan must be re-made and explained, or escalated when the protocol can no longer be met.

## 2. How Track 3 is covered

| Track 3 asks for | Where it is in RESQ AI |
| --- | --- |
| Data | 9 scenario tables read with SQL through **Zetaris** (`resq/tools/zetaris.py`), rainfall from the Open-Meteo archive |
| Knowledge | Numbered protocol rules `P1`–`P8` (`docs/protocol.md`, `resq/protocol.py`), cited as evidence in plans |
| Memory / state | **Meterless World Model**: scenario entities, verified facts with provenance, risk assessments, coordinator events and every published plan |
| Reasoning | Six agents in a LangGraph graph with a critique loop (`resq/graph.py`) |
| Reliable decisions and actions | Hard rules in code (`validate_plan`), feasibility check, bounded retries, escalation to a human with the exact gap |

## 3. The agent graph

```text
question / coordinator event
  ▼
Intake (rules) ── why ─────────────────────────────────────────────► Explainer
  ▼
Reconciler ── P1 scores in code; model decides contested objects ─► World Model facts
  ▼
Risk Analyst ── P3 risk + P4 needs in code; model writes summary ─► World Model facts
  ├── situation ────────────────────────────────────────────────────► Explainer
  ▼
Planner (model) ── delivery tier per community (P4.1)
  │   code: risk order (P5.1), critical minimum first (P5.2), vehicle packing (P6)
  ▼
Critic ── validate_plan (code) + feasibility (code) + reasons review (model, once)
  │   rejected → Planner with concrete feedback (max 3 rounds)
  │   infeasible / still rejected / low confidence → escalated
  ▼
Explainer ── exact diff + causing events (code) + coordinator report (model) ─► plan_published
```

**Principle: the model decides and explains; code computes.** The split, agent by agent:

| Agent | The model decides | Code computes |
| --- | --- | --- |
| Reconciler | Which status of a contested object to believe, with a reason (it may only pick a reported status or `uncertain`) | Reliability × recency score per reported status (P1), confidence, evidence ids |
| Risk Analyst | Situation summary for the coordinator | Risk index (P3), needs (P4), reachability via routing |
| Planner | Delivery tier per community under scarcity (`full` / `essential` / `minimum` / `none`) | Quantities, delivery order, stock limits, vehicle packing and routes |
| Critic | Whether the reasons hold (priority inversions, wrong facts) | Every hard rule: capacity, trips, stock, passability, shortest route, critical minimum, priority order |
| Explainer | The report | The exact plan diff and the events that caused it |

Why tiers instead of quantities: with free-form quantities the fast Nemotron model invented decreasing coverages and exceeded stock; discrete tiers keep the decision with the model and the arithmetic in code (decision log, `AGENTS.md` §10).

## 4. Critique, revision and escalation

- **Hard rules** (`resq/tools/validators.py`): vehicle home warehouse (P6.1), per-trip and two-trip capacity (P6.2), routes equal to `best_route` (P6.3), stock (P6.4), passability (P2), critical minimum of water and food (P5.2), risk order (P5.1), unserved consistency (P5.4).
- **Feasibility** (`critical_minimum_gaps`): when P5.2 cannot be met at all, the Critic stops looping and escalates with the exact gap instead of asking for the impossible.
- **Model review**: can send a plan back once (P8.2); later remarks are notes, so the loop always ends.
- **Escalation** (P8.3): still rejected after 3 rounds, a critical community unreachable, infeasible minimum, or plan confidence below 0.5. The plan keeps its best effort and lists the reasons.

Example from the scenario: after the coordinator blocks **T6**, the river valley is reachable only by fording vehicles. The critical communities need at least **17,952 kg** of water and food; the fording vehicles carry **13,800 kg** in two trips. The re-plan delivers what fits, in risk order, and is escalated with that sentence as the reason.

## 5. Meterless World Model: what it does here

`world_service/` runs the Meterless World Model reference implementation (vendored, Apache-2.0, conformance **8/8**: `npm run conformance`) behind a small HTTP API. `resq/world/` is the Python client every agent uses.

| What is stored | How |
| --- | --- |
| Scenario rows (communities, segments, vehicles, …) | Entities with external keys `type:resq:id`, seeded from Zetaris; unchanged rows are skipped |
| Agent conclusions (verified statuses, risk assessments) | Facts with provenance: source kind, agent, observation time, confidence, evidence report ids, reason |
| Coordinator actions (block / reopen a segment) | Facts from source `coordinator`, confidence 1.0 |
| Published plans | One fact per plan version |

What the engine gives the agents:

- **Shared state**: routing, validators and every agent read `world.get_state()`; nobody passes domain state around by hand.
- **Conflict policy**: for a predicate, the most recent *observation* wins. A reconciler conclusion written later but observed earlier cannot undo a coordinator block.
- **History-driven explanations**: the Explainer compares the plan with the previous version and finds the status changes recorded after it (`world.history()`).
- **Point in time**: `world.get_state(as_of="2020-11-05T10:00")` returns what the system believed then.
- **Audit**: every mutation is in the engine's audit log (`world.audit()`).

Inspect it live:

```bash
python -m resq.world summary
python -m resq.world timeline T7
python -m resq.world state --at 2020-11-05T10:00
python -m resq.world audit --last 15
```

## 6. Zetaris: the only data source

The scenario lives in our own Postgres (`docker-compose.yml`), registered in Zetaris as the datasource `resq_pg` (`scripts/register_zetaris.py`). The agents run Lightning SQL through Zetaris' REST API, one statement per request:

| Query | Used by |
| --- | --- |
| `SELECT * FROM resq_pg.<table>` for 7 tables | `scenario.load_tables` → World Model seed |
| `SELECT MAX(datetime) … FROM resq_pg.rainfall`, `SELECT MAX(timestamp) … FROM resq_pg.field_reports` | scenario clock (decision time) |
| `SELECT * FROM resq_pg.field_reports ORDER BY timestamp, id` | Reconciler |
| `SELECT SUM(precipitation_mm) … FROM resq_pg.rainfall WHERE datetime > …` | Risk Analyst (rain in the last 24 h) |

`SAMPLE_MODE=true` runs the same SQL on SQLite loaded from `data/sample/`, so the agent code is identical with and without Zetaris; every query returns the same rows on both.

## 7. Models: Nightshift → Nemotron

All model calls go through `resq/llm.py` (OpenAI-compatible client, `meterless-app` headers, 90 s timeout, 2 retries, JSON repair round). Two lanes: **fast** (Reconciler, Risk Analyst, Explainer; temperature 0) and **deep** (Planner, Critic). Nemotron's thinking is turned off unless `LANE_DEEP_THINKING=true`, because with thinking a plan request spent its whole budget reasoning or exceeded the timeout.

## 8. Traceability

Every agent step appends one JSONL line to `logs/trace_<run_id>.jsonl`: `ts, run_id, agent, input_summary, output_summary, lane, model, duration_ms, iteration`. The Critic's rounds appear as `planner`/`critic` pairs with increasing `iteration`. Example traces are in `output_examples/`.

## 9. How to check these claims

| Claim | Check |
| --- | --- |
| Tests pass offline | `pytest` |
| World Model conformance | `cd world_service && npm run conformance` |
| Data comes from Zetaris | `python scripts/register_zetaris.py --verify`, then a run with `SAMPLE_MODE=false` |
| Critique and escalation | `python scripts/run_demo.py`, then read `output_examples/*_trace.jsonl` and `02_block_T6_report.md` |
| Robustness across runs | `python scripts/heavy_test.py --runs 5` |
| State evolution | `python -m resq.world timeline T6` after a run |
