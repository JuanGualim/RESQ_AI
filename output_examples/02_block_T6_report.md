# Flood Emergency Plan Update

## Situation
- Segment **T6** is blocked, cutting access for communities reachable only by fording vehicles.
- Five communities remain **critical risk**: C07 El Zapotal (isolated, risk 0.81), C12 El Paraiso (reachable by ford, risk 0.789), C03 Los Amates (reachable by ford, risk 0.749), C05 Playitas (evacuating, risk 0.705), and C04 Las Pozas (reachable by ford, risk 0.664).
- Four communities are **unserved** due to zero stock coverage: C01 Cerro Verde, C06 Rio Blanco, C08 El Mirador, C11 Nuevo Esfuerzo.

## Plan
- **Tier 1 (essential):** C07 El Zapotal and C12 El Paraiso receive delivered stock first; both are reachable by ford and have essential-tier coverage fitting remaining reserves.
- **Tier 2:** C03 Los Amates receives next allocation; also reachable by ford and fits remaining stock after Tier 1.
- **Tier 3:** C05 Playitas receives minimum tier while evacuating; stock conserved for higher-ranked communities.
- **Tier 4:** C04 Las Pozas receives minimum tier after C05 stock is exhausted.
- Unserved communities (C01, C06, C08, C11) receive no allocation due to zero coverage and lower risk scores.

## Why the plan changed
The segment **T6** was blocked on 2020-11-05, preventing fording vehicles from reaching C03, C04, C05, and C07. This forced a reordering of deliveries to prioritize communities still accessible by ford (C07, C12, C03) and shift C04 to a lower tier after C05 exhausts stock, respecting vehicle capacity limits of 13,800 kg against a critical need of 18,337 kg.

## Risks and decisions for you
- **Escalation needed:** `escalated` is `true`. A human decision is required because critical communities (C03, C04, C05, C07, C12) need 18,337 kg but fording vehicles can carry only 13,800 kg. Verify vehicle availability and rerouting options.
- Verify that C07’s isolated status and C05’s evacuation route to S4 Centro Deportivo Los Amates (8.8 km) are current.
- Confirm that 95 of 211 water units for C04 and all 211 food kits, 22 medical kits for C04, and 122 water units for C07 could not be carried due to capacity shortfalls.

### Exact changes vs plan v1

- C03 blanket: removed (was 40 units, V1 via T3-T6)
- C03 food_kit: 80 -> 40 units; V1 via T3-T6, V1 via T3-T6 -> V2 via T3-T7-T8
- C03 hygiene_kit: removed (was 20 units, V1 via T3-T6)
- C03 medical_kit: 4 -> 4 units; V1 via T3-T6 -> V2 via T3-T7-T8
- C03 water_20l: 80 -> 40 units; V1 via T3-T6, V1 via T3-T6 -> V2 via T3-T7-T8
- C04 food_kit: removed (was 127 units, V1 via T3-T6-T8, V5 via T1-T3-T6-T8)
- C04 medical_kit: removed (was 13 units, V1 via T3-T6-T8, V5 via T1-T3-T6-T8)
- C04 water_20l: 127 -> 116 units; V1 via T3-T6-T8, V5 via T1-T3-T6-T8 -> V4 via T1-T3-T7, V6 via T1-T3-T7, V6 via T1-T3-T7
- C05 blanket: removed (was 124 units, V1 via T3-T6-T10-T11-T12)
- C05 food_kit: 248 -> 124 units; V2 via T3-T7-T9, V6 via T1-T3-T7-T9, V6 via T1-T3-T7-T9, V1 via T3-T6-T10-T11-T12 -> V2 via T3-T7-T9, V4 via T1-T3-T7-T9, V4 via T1-T3-T7-T9
- C05 hygiene_kit: removed (was 62 units, V1 via T3-T6-T10-T11-T12)
- C05 medical_kit: 13 -> 13 units; V2 via T3-T7-T9 -> V2 via T3-T7-T9, V4 via T1-T3-T7-T9
- C05 water_20l: 248 -> 124 units; V2 via T3-T7-T9, V4 via T1-T3-T7-T9, V4 via T1-T3-T7-T9, V6 via T1-T3-T7-T9 -> V2 via T3-T7-T9
- C07 blanket: removed (was 122 units, V1 via T3-T6-T10-T11)
- C07 food_kit: 244 -> 122 units; V2 via T3-T7-T9-T12, V2 via T3-T7-T9-T12, V1 via T3-T6-T10-T11 -> V2 via T3-T7-T9-T12
- C07 hygiene_kit: 61 -> 1 units; V2 via T3-T7-T9-T12, V1 via T3-T6-T10-T11 -> V4 via T1-T3-T7-T9-T12
- C07 water_20l: 244 -> 122 units; V2 via T3-T7-T9-T12, V2 via T3-T7-T9-T12, V1 via T3-T6-T10-T11 -> V2 via T3-T7-T9-T12
- C12 blanket: removed (was 64 units, V1 via T3-T6-T10-T20)
- C12 food_kit: 128 -> 64 units; V1 via T3-T6-T10-T20, V1 via T3-T6-T10-T20 -> V2 via T3-T7-T9-T12-T21
- C12 hygiene_kit: removed (was 32 units, V1 via T3-T6-T10-T20)
- C12 medical_kit: 13 -> 13 units; V1 via T3-T6-T10-T20 -> V2 via T3-T7-T9-T12-T21
- C12 water_20l: 128 -> 64 units; V1 via T3-T6-T10-T20, V1 via T3-T6-T10-T20 -> V2 via T3-T7-T9-T12-T21
- C06: now unserved

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
