# Flood Emergency: Resource Assignment Report

## Situation
- **C07 El Zapotal** remains isolated with critical risk 0.81; all assigned resources (water, food, medical, hygiene) routed via fordable T3-T7-T9-T12.
- **C12 Los Alamos** has critical risk 0.789; resources reachable by ford via T3-T7-T9-T12-T21.
- **C03 Loma Alta**, **C04 Pueblo Nuevo**, and **C05 Playitas** show declining risk scores (0.749→0.664) but face capacity constraints.
- Four communities (**C01, C06, C08, C11**) are unserved due to insufficient stock and vehicle capacity.

## Plan
Resources are prioritized by risk score and fordability:
1. **C07** (risk 0.81) receives water, food, and medical kits via vehicle V2 on route T3-T7-T9-T12.
2. **C12** (risk 0.789) receives identical resource sets via V2 on T3-T7-T9-T12-T21.
3. **C03, C04, C05** follow in descending risk order, with remaining stock allocated via available vehicles (V2, V4, V6) respecting fording limits.
4. All assignments reference evidence tags (e.g., R006, R019, R025) and prioritize essential tiers that respect stock conservation.

## Why the plan changed
The plan was revised because segment **T6 was blocked** (event seq 93, type segment_blocked), forcing reroutes from V1/T3-T6 paths to V2/V4/T3-T7 alternatives. This blockage directly caused the removal of C03/C04/C05/V1 routes and the shift to V2/T3-T7-T8 and V4/T1-T3-T7 assignments, as the system could no longer use the blocked T6 corridor for any community.

## Risks and decisions for you
- **Escalation needed**: `escalated: true` — a human decision is required because critical communities (C03–C07, C12) collectively need 18,337 kg but fording vehicles can only carry 13,800 kg. Verify whether to offload non-essential items, request additional transport, or adjust priority tiers.
- **Capacity gaps**: C04 water_20l (95 of 211 units undelivered), C04 food_kit (211 of 211 undelivered), and C07 hygiene_kit (60 of 61 units undelivered) remain unserved despite assignments.
- **Route verification**: Confirm that all assigned routes (T3-T7-T9-T12, T3-T7-T9-T12-T21, T3-T7-T8) are passable given the T6 blockage and current water levels.