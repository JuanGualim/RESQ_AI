# RESQ AI demo video script

Target length: 3 minutes 40 seconds. Record the live demo on Nightshift with the World Model and Zetaris connected. Keep the cursor still unless an action is being demonstrated.

## 0:00–0:25 — The decision problem

**On screen:** Title, then the baseline dashboard.

**Voice-over:**

> During a flood, a municipal coordinator receives reports that are fast, incomplete, and often contradictory. A distribution plan can become unsafe minutes after it is approved. RESQ AI helps the coordinator build a protocol-based aid plan, revise it when conditions change, and understand exactly why the decision changed.

## 0:25–1:20 — Build the first plan

**Action:** Select the baseline scenario and click **Plan now**.

**On screen:** Road map, plan version, assignment table, confidence, and agent trace.

**Voice-over:**

> The system reads the scenario through Zetaris. The Reconciler weighs conflicting field reports by source reliability and recency. The Risk Analyst computes exposure, vulnerability, dependent population, isolation, and reported need. The Planner chooses delivery tiers, while deterministic code calculates quantities, routes, stock, and vehicle capacity. The Critic checks the result against protocol rules and can send it back for revision.

**Pause on:** One contested road and one critic revision in the trace.

> The trace makes the multi-agent reasoning visible: who acted, which round ran, how long it took, and what changed.

## 1:20–2:20 — Live re-plan after T6 is blocked

**Action:** Select `T6`, then click **Block segment**.

**On screen:** T6 changes to blocked, routes update, plan version changes from v1 to v2, and the escalation banner appears.

**Voice-over:**

> Now the coordinator reports that segment T6 is blocked. This event is authoritative and is written to the Meterless World Model. RESQ AI does not patch the old answer. It reconciles the new state, recomputes reachability and risk, rebuilds the distribution plan, and reviews it again.

> The new plan is escalated because the critical minimum cannot be carried by the vehicles that can still reach the affected communities. The interface shows the exact P8.3 reason instead of hiding the limitation.

**Action:** Click **Why did the plan change?**

> Because the World Model keeps versioned facts and events, the Explainer can identify the causing event and produce an exact plan diff: what moved, what was removed, and why.

## 2:20–3:10 — Architecture and sponsor technology

**On screen:** Architecture slide, followed briefly by lane/provider information in the trace.

**Voice-over:**

> RESQ AI is a LangGraph multi-agent system with bounded critique and revision. Zetaris is the only scenario data source in the full deployment. Meterless Nightshift provides the OpenAI-compatible model runtime, pinned to NVIDIA Nemotron for the demo. The Meterless World Model is the shared domain state and event history used by every agent. Deterministic Python tools handle routing, capacity, inventory, and hard protocol validation.

> The model decides and explains. The code computes and verifies.

## 3:10–3:40 — Outcome and limits

**On screen:** Final v2 dashboard with the escalation and trace visible.

**Voice-over:**

> The coordinator receives a plan that is actionable, versioned, and honest about uncertainty. RESQ AI does not replace emergency leadership; it makes changing evidence, protocol constraints, and trade-offs inspectable under time pressure. This hackathon version uses synthetic municipal data and a simplified fictional protocol. Our next steps are live field integrations, stronger scenario evaluation, and user testing with emergency coordinators.

**End card:** `RESQ AI — plans that change when reality does.`

## Recording checklist

- Use the real Nightshift, World Model, and Zetaris services.
- Confirm the trace shows the pinned Nemotron model and the expected lanes.
- Reset state before recording so the baseline is plan v1.
- Rehearse the T6 event and confirm the escalation reason is visible without scrolling.
- Do not show `.env`, tokens, local IP addresses, or service credentials.
- Keep the final export between 1 and 4 minutes.
