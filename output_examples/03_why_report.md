# Flood Emergency Plan Report

## Situation
- Critical risk communities (C07, C12, C03, C05, C04) require ford-only vehicle access due to road conditions.
- Segment T6 is blocked, disrupting routes that previously used this path.
- Multiple communities are isolated or evacuating with limited shelter capacity.
- Stock exhaustion has occurred across water, food, medical, and hygiene resources.

## Plan
- **Priority 1-3**: Community C07 receives water_20l (122), food_kit (122), and medical_kit (25) via vehicle V2 using route T3-T7-T9-T12. This community is isolated and ford_only; essential tier respects stock limits while delivering core needs.
- **Priority 4-6**: Community C12 receives water_20l (64), food_kit (64), and medical_kit (13) via vehicle V2 using route T3-T7-T9-T12-T21. Critical risk 0.789, needs_aid, ford_only; essential tier after C07 respects remaining stock.
- **Priority 7-9**: Community C03 receives water_20l (40), food_kit (40), and medical_kit (4) via vehicle V2 using route T3-T7-T8. Critical risk 0.749, needs_aid, ford_only; essential tier after C12 respects remaining stock.
- **Priority 10-12**: Community C05 receives water_20l (124), food_kit (6-83 depending on origin), and medical_kit (1-12) via vehicles V2 and V4. Critical risk 0.705, evacuating, ford_only; minimum tier due to stock exhaustion after C03.
- **Priority 13**: Community C04 receives water_20l (26-45) via vehicles V4 and V6 using route T1-T3-T7. Critical risk 0.664, needs_aid, ford_only; minimum tier after C05 exhausts remaining stock.

## Why the plan changed
The plan changed because segment T6 was blocked by the coordinator, forcing route adjustments for communities that previously relied on this path. Specifically: C03 resources shifted from V1 via T3-T6 to V2 via T3-T7-T8; C04 resources changed from V1/V5 via T3-T6-T8 to V4/V6 via T1-T3-T7; C05 routes were reorganized across vehicles V2, V4, and V1; and C06 is now unserved as its only route depended on the blocked T6 segment. These adjustments reflect the necessity of rerouting around the blocked segment.

## Risks and decisions for you
- **Escalation needed**: escalated is true. Escalation reasons: ["P5.2 infeasible: critical communities reachable only by fording vehicles (C03, C04, C05, C07, C12) need at least 17,952 kg; fording vehicles carry 13,800 kg"]. A human decision is needed because total resource weight required by critical ford-only communities exceeds vehicle capacity.
- **Verify**: T6 blockage status and alternate route availability; shelter capacity at S4 Centro Deportivo Los Amates for evacuating communities; actual stock levels versus assigned quantities; vehicle capacity limits for fording versus non-fording vehicles.