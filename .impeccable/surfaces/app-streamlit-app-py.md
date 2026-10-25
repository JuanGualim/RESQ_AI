---
version: 1
slug: "app-streamlit-app-py"
primary_target: "app/streamlit_app.py"
related_targets: []
---

# RESQ AI operations dashboard

Mode: Operate

Audience: a municipal emergency coordinator reviewing and revising flood-aid distribution under time pressure.

Task: compare example plans or run the live multi-agent workflow; inspect routes, assignments, escalation, reports, and trace; block a road segment; ask why a plan changed.

Constraints: Streamlit, desktop-first but responsive, offline examples remain usable, all UI copy is English, color never carries road state alone, and live failures must preserve the last usable result.

## Direction contract

**THESIS:** A live dispatch board turns multi-agent decisions into rows the coordinator can scan, compare, and trust. It refuses the generic metric-card dashboard: the assignment board, current road state, and escalation are the interface's primary structure.

**OWN-WORLD:** Matte near-black surfaces, cool steel dividers, warm white operational text, amber for attention, and red only for blocked or escalated states. Condensed uppercase display type labels the board; readable sans-serif supports reports and long reasons. Subtle split seams and ruled rows create rhythm without imitating physical controls.

**STORY:** The coordinator first sees whether the plan is active or escalated, then reads the road network and ordered dispatch rows, acts on the incident, and opens the report or trace for evidence. A segment block visibly propagates into route, row, and plan-version changes.

**FIRST VIEWPORT:** A slim command header carries product, scenario, version, confidence, and mode. Below it, the road map occupies the left half and the current decision with live actions occupies the right. The assignment board begins in the same viewport; report and trace continue below. The signature move is a brief staggered row highlight after the selected plan changes.

**FORM:** Code-led Operate surface; chosen direction is Live Dispatch Board, derived from the split-flap concourse system. Standard Streamlit controls remain familiar while palette, density, type, and row-update motion carry the world. seed:190a3712a49f0cd2

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Unresolved decisions: none for the first implementation.
