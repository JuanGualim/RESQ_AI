# RESQ AI flood response protocol

Domain rules the agents follow and cite as evidence (`P1`…`P8`). The numbers here are mirrored in `resq/protocol.py`; change both together and log the change in `AGENTS.md` §10.

This protocol is fictional and simplified for the hackathon scenario. It is inspired by common humanitarian practice (prioritize the most exposed and most dependent people, verify reports before acting) but is not an official standard.

## P1. Source reliability (reconciling field reports)

Field reports contradict each other. The Reconciler scores every reported status of an object (road segment, shelter, community):

| Source | Weight | Why |
| --- | --- | --- |
| `brigade` | 0.9 | Direct observation on the ground |
| `official` | 0.7 | Authoritative but bulletins are often stale |
| `social_media` | 0.3 | Fast but unverified; may be rumor |

- **Recency:** each report's weight is multiplied by `0.5 ^ (age_hours / 2)`, where `age_hours` is measured from the latest report in the dataset (half-life of 2 hours).
- **Score per status** = sum of the decayed weights of the reports for that status.
- **Verified status** = the status with the highest score. **Confidence** = winner score / total score.
- **P1.1** If confidence is below **0.6**, the status is `uncertain`. An uncertain road segment is treated as passable only by vehicles that can ford, and it is listed in the plan's risks.
- **P1.2** Coordinator events entered in the UI (for example, blocking a segment) are authoritative: confidence 1.0, and they override any earlier report.

## P2. Road segment passability

| Verified status | Who can pass |
| --- | --- |
| `open`, `damaged` | Every vehicle |
| `passable_4x4`, `flooded`, `uncertain` | Only vehicles with `can_ford = true` |
| `closed`, `blocked` | Nobody |

## P3. Risk index per community

Computed in code (`resq/agents/risk_analyst.py`), between 0 and 1:

```text
risk = 0.30 * exposure + 0.25 * vulnerability + 0.20 * dependents + 0.15 * isolation + 0.10 * reported_need
```

| Factor | Definition |
| --- | --- |
| `exposure` | `elevation_factor * rain_factor`. Elevation: ≤15 m → 1.0 · ≤25 m → 0.8 · ≤50 m → 0.5 · ≤100 m → 0.25 · higher → 0.1. Rain in the last 24 h: ≥100 mm → 1.0 · ≥50 mm → 0.8 · ≥20 mm → 0.5 · less → 0.3 |
| `vulnerability` | `(vulnerability - 1) / 4` |
| `dependents` | `min(1, (pct_children + pct_elderly) / 55)` |
| `isolation` | 1.0 if no vehicle can reach it from any warehouse · 0.6 if only fording vehicles can · 0 otherwise |
| `reported_need` | Verified community status: `isolated` or `evacuating` → 1.0 · `needs_aid` → 0.7 · `stable` or no reports → 0 |

**Levels:** `critical` ≥ 0.60 · `high` ≥ 0.45 · `medium` ≥ 0.30 · `low` below.

## P4. Needs per community (one 24-hour delivery round)

- **Covered population:** critical 100 %, high 60 %, medium 30 %, low 0 % of the population.
- **Families** = ceil(covered population / 5).

| Resource | Need |
| --- | --- |
| `water_20l` | 1 per family (≈ 4 L per person per day) |
| `food_kit` | 1 per family |
| `hygiene_kit` | 1 per 2 families |
| `medical_kit` | 1 per 50 covered people if `pct_elderly` ≥ 10 or the community is `isolated`; otherwise 1 per 100 |
| `blanket` | 1 per family, only for `critical` communities |

A community whose verified status is `stable` gets half the need (it reported its own supplies).

## P5. Allocation priority

- **P5.1** Serve communities in descending risk order.
- **P5.2** Every `critical` community must receive water and food (at least 50 % of its need of each) before any `medium` community receives anything.
- **P5.3** When stock is short, `water_20l` comes first, then `food_kit`, `medical_kit`, `hygiene_kit`, `blanket`.
- **P5.4** Communities that cannot be reached (P2) go to `unserved` with the reason; they are never assigned a route.

## P6. Vehicles and routes

- **P6.1** A vehicle starts from its home warehouse (`vehicles.warehouse_id`) and only carries that warehouse's stock.
- **P6.2** A vehicle makes at most **2 trips** per round. The total load assigned to a vehicle cannot exceed `2 * capacity_kg`, and a single assignment cannot exceed `capacity_kg`.
- **P6.3** Every route is computed by `best_route` (shortest distance that respects P2). Agents never invent routes.
- **P6.4** Total quantity assigned per warehouse and resource cannot exceed the inventory.

## P7. Shelters

- **P7.1** A shelter whose verified status is `flooded` cannot receive people. A shelter at 95 % of capacity or more is `full`.
- **P7.2** When a community is `critical` and `evacuating` or `isolated`, the plan's risks recommend the nearest shelter with free capacity.

## P8. Evidence, review and escalation

- **P8.1** Every assignment's `reason` cites evidence: field report IDs (`R0xx`), protocol rules (`P#`) or the computed risk.
- **P8.2** The Critic rejects a plan that breaks any hard rule (P2, P5.2, P5.4, P6) and sends concrete feedback to the Planner, at most **3 rounds**.
- **P8.3** The plan is **escalated to a human decision** when the Critic still rejects it after 3 rounds, when a `critical` community cannot be served, or when the plan's confidence is below **0.5**.
