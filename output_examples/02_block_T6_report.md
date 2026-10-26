## Situation
- Five critical communities (C07, C12, C03, C05, C04) are served in priority order by risk score, all with ford-only reachability.
- C06 (high risk, score 0.597) and medium-risk communities C01, C08, C11 remain unserved due to stock exhaustion and protocol restrictions.
- A segment blockage on T6 has occurred since the previous plan version.

## Plan
- Allocation follows critical-first protocol P5.1/P5.2: C07 (122 water_20l, 122 food_kit), C12 (64 water_20l, 64 food_kit), C03 (40 water_20l, 40 food_kit), C05 (124 water_20l, 124 food_kit), C04 (116 water_20l only).
- C06 receives no deliveries; its water_20l and food_kit stock was exhausted during P6.2 (0 of 7 units).
- Medium-risk communities C01, C08, C11 are unserved per protocol.

## Why the plan changed
The plan version increased from 1 to 2 following a segment_blocked event on T6, which restricted vehicle access and contributed to stock shortfalls affecting C05 and C06.

## Risks and decisions for you
- **Escalation is required**: P8.3 states that critical communities reachable only by fording vehicles need at least 18,337 kg, but fording vehicles carry only 13,800 kg. This weight shortfall makes the current plan infeasible and requires a human decision.
- **Risks to verify**: P1.2 (T6 blocked by the coordinator), P7.1 (shelter S2 full), P7.2 (C05 and C07 nearest shelters at 4.8 km and 8.8 km respectively), P6.2 stock exhaustion for C05 (233/248 water_20l, 234/248 food_kit) and C06 (0/7 water_20l, 0/7 food_kit).

### Exact changes vs plan v1

- C03 blanket: removed (was 80 units, V1 via T3-T6)
- C03 food_kit: 80 -> 40 units; V1 via T3-T6, V1 via T3-T6 -> V2 via T3-T7-T8
- C03 hygiene_kit: removed (was 40 units, V1 via T3-T6)
- C03 medical_kit: 4 -> 4 units; V1 via T3-T6 -> V2 via T3-T7-T8
- C03 water_20l: 80 -> 40 units; V1 via T3-T6, V1 via T3-T6 -> V2 via T3-T7-T8
- C04 food_kit: removed (was 127 units, V1 via T3-T6-T8, V5 via T1-T3-T6-T8)
- C04 medical_kit: removed (was 13 units, V1 via T3-T6-T8, V5 via T1-T3-T6-T8)
- C04 water_20l: 127 -> 116 units; V1 via T3-T6-T8, V5 via T1-T3-T6-T8 -> V4 via T1-T3-T7, V6 via T1-T3-T7, V6 via T1-T3-T7
- C05 blanket: removed (was 124 units, V1 via T3-T6-T10-T11-T12, V5 via T1-T3-T6-T10-T11-T12)
- C05 food_kit: 248 -> 124 units; V2 via T3-T7-T9, V6 via T1-T3-T7-T9, V6 via T1-T3-T7-T9, V1 via T3-T6-T10-T11-T12 -> V2 via T3-T7-T9, V4 via T1-T3-T7-T9, V4 via T1-T3-T7-T9
- C05 hygiene_kit: removed (was 62 units, V1 via T3-T6-T10-T11-T12)
- C05 medical_kit: 13 -> 13 units; V2 via T3-T7-T9 -> V2 via T3-T7-T9, V4 via T1-T3-T7-T9
- C05 water_20l: 248 -> 124 units; V2 via T3-T7-T9, V4 via T1-T3-T7-T9, V4 via T1-T3-T7-T9, V6 via T1-T3-T7-T9 -> V2 via T3-T7-T9
- C06 food_kit: removed (was 7 units, V5 via T1-T3-T6-T10)
- C06 medical_kit: removed (was 2 units, V5 via T1-T3-T6-T10)
- C06 water_20l: removed (was 7 units, V5 via T1-T3-T6-T10)
- C07 blanket: removed (was 244 units, V1 via T3-T6-T10-T11)
- C07 food_kit: 244 -> 122 units; V2 via T3-T7-T9-T12, V2 via T3-T7-T9-T12, V1 via T3-T6-T10-T11 -> V2 via T3-T7-T9-T12
- C07 hygiene_kit: 122 -> 1 units; V2 via T3-T7-T9-T12, V1 via T3-T6-T10-T11 -> V4 via T1-T3-T7-T9-T12
- C07 water_20l: 244 -> 122 units; V2 via T3-T7-T9-T12, V2 via T3-T7-T9-T12, V1 via T3-T6-T10-T11 -> V2 via T3-T7-T9-T12
- C12 blanket: removed (was 128 units, V1 via T3-T6-T10-T20)
- C12 food_kit: 128 -> 64 units; V1 via T3-T6-T10-T20, V1 via T3-T6-T10-T20 -> V2 via T3-T7-T9-T12-T21
- C12 hygiene_kit: removed (was 64 units, V1 via T3-T6-T10-T20)
- C12 medical_kit: 13 -> 13 units; V1 via T3-T6-T10-T20 -> V2 via T3-T7-T9-T12-T21
- C12 water_20l: 128 -> 64 units; V1 via T3-T6-T10-T20, V1 via T3-T6-T10-T20 -> V2 via T3-T7-T9-T12-T21

### Assignments (plan v2)

| # | Community | Resource | Qty | Vehicle | From | Route |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | C07 | water_20l | 122 | V2 | W1 | T3-T7-T9-T12 |
| 2 | C07 | food_kit | 122 | V2 | W1 | T3-T7-T9-T12 |
| 3 | C07 | medical_kit | 25 | V2 | W1 | T3-T7-T9-T12 |
| 4 | C12 | water_20l | 64 | V2 | W1 | T3-T7-T9-T12-T21 |
| 5 | C12 | food_kit | 64 | V2 | W1 | T3-T7-T9-T12-T21 |
| 6 | C12 | medical_kit | 13 | V2 | W1 | T3-T7-T9-T12-T21 |
| 7 | C03 | water_20l | 40 | V2 | W1 | T3-T7-T8 |
| 8 | C03 | food_kit | 40 | V2 | W1 | T3-T7-T8 |
| 9 | C03 | medical_kit | 4 | V2 | W1 | T3-T7-T8 |
| 10 | C05 | water_20l | 124 | V2 | W1 | T3-T7-T9 |
| 11 | C05 | food_kit | 6 | V2 | W1 | T3-T7-T9 |
| 11 | C05 | food_kit | 83 | V4 | W2 | T1-T3-T7-T9 |
| 11 | C05 | food_kit | 35 | V4 | W2 | T1-T3-T7-T9 |
| 12 | C05 | medical_kit | 1 | V2 | W1 | T3-T7-T9 |
| 12 | C05 | medical_kit | 12 | V4 | W2 | T1-T3-T7-T9 |
| 13 | C04 | water_20l | 26 | V4 | W2 | T1-T3-T7 |
| 13 | C04 | water_20l | 45 | V6 | W2 | T1-T3-T7 |
| 13 | C04 | water_20l | 45 | V6 | W2 | T1-T3-T7 |
| 18 | C07 | hygiene_kit | 1 | V4 | W2 | T1-T3-T7-T9-T12 |
