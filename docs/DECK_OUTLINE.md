# RESQ AI deck outline

Recommended length: 10 slides. Use one operational screenshot or diagram per slide and keep body copy to three short points or fewer.

## 1. RESQ AI

- Flood aid planning that updates when reality changes
- Open Agent Hackathon 2026 · Track 3: Reasoning Architecture
- Team names and roles

**Visual:** Final dashboard with the map, plan status, and escalation visible.

## 2. The coordination problem

- Field reports contradict each other.
- Roads and shelter conditions change after a plan is published.
- Inventory, vehicle capacity, and protocol constraints must still hold.

**Visual:** Three conflicting reports about one segment converging on one coordinator decision.

## 3. What RESQ AI delivers

- A versioned aid distribution plan with assignments and routes
- Visible confidence, risks, evidence, and protocol citations
- A re-plan and exact explanation after a coordinator event

**Visual:** Baseline v1 beside blocked-road v2, with three changed items called out.

## 4. The live workflow

1. Review the current plan and road network.
2. Block a segment or request a new plan.
3. Inspect the revised plan, trace, and escalation reason.

**Visual:** Three-step product flow using real UI screenshots.

## 5. A real multi-agent reasoning loop

- Intake → Reconciler → Risk Analyst → Planner → Critic → Explainer
- Critique and revision are bounded to three rounds.
- Infeasible or low-confidence plans escalate to a human.

**Visual:** The architecture graph from `AGENTS.md`, simplified for presentation.

## 6. The World Model makes change explainable

- Scenario rows become entities.
- Agent conclusions and coordinator actions become facts with provenance.
- Event history connects a changed road to a changed plan.

**Visual:** `segment_blocked:T6` flowing into verified state, plan v2, and the explanation diff.

## 7. LLM judgment, deterministic computation

- Nemotron reconciles contested reports, chooses delivery tiers, reviews reasons, and explains.
- Code computes risk, quantities, shortest routes, packing, inventory, and hard-rule validation.
- This boundary improves reliability and makes failures testable.

**Visual:** A split diagram with “decide and explain” on one side and “compute and verify” on the other.

## 8. Sponsor technology

- **Zetaris:** the full deployment's only scenario data source, queried with SQL
- **Meterless:** Nightshift model runtime and World Model shared state
- **NVIDIA:** Nemotron models pinned for the demo
- **Cursor / Codex / Claude Code:** collaborative development workflow

**Visual:** Architecture stack with each sponsor attached to the component it actually powers.

## 9. Evidence that it works

- World Model conformance: 8/8
- Offline automated test suite and reproducible sample scenario
- Baseline, blocked-road, explanation, plans, reports, and JSONL traces committed as examples

**Visual:** Test result, conformance result, and trace excerpt. Refresh the test count immediately before submission.

## 10. Impact, limitations, and next steps

- Faster inspection of complex allocation decisions under changing conditions
- Current limits: synthetic data, simplified protocol, variable model judgments
- Next: Nightshift evaluation runs, live data deployment, and coordinator usability testing

**Visual:** The final escalated plan with “Human decision required” as the closing message.
