# HackOS submission draft

Text ready to paste into the HackOS submission form, plus the final checklist. Items marked **[team]** need a person to fill or confirm them before submitting. Hard deadline: **27 October 2026, 23:45 UTC (17:45 Guatemala)**; internal target 12:00 Guatemala.

## Project

- **Name:** RESQ AI
- **Track:** Reasoning Architecture (Track 3)
- **Tagline:** Flood aid decisions that re-plan themselves and explain why.
- **Repository:** https://github.com/JuanGualim/RESQ_AI (**make it public before submitting**)
- **Demo video:** **[team]** link (1–4 min)
- **Slide deck:** **[team]** link

### One-sentence problem statement

We are building an agent system that helps a municipal emergency coordinator decide how to distribute scarce aid during a flood, by reconciling contradictory field reports, scoring each community's risk under a written protocol and planning deliveries that a critic agent checks, using scenario data served by Zetaris, and producing a versioned distribution plan that is re-planned when a road is blocked, with what changed and why, or escalated to a human when the protocol can no longer be met.

### Short description

During a flood, field reports contradict each other, supplies and vehicles do not cover every need, and a plan goes stale as soon as a road closes. RESQ AI is a six-agent LangGraph system: an Intake agent routes the request; a Reconciler weighs official, brigade and social-media reports by reliability and recency and lets Nemotron decide the contested ones; a Risk Analyst scores every community; a Planner chooses delivery tiers under scarcity; a Critic enforces the protocol's hard rules in code and reviews the reasons, sending plans back for revision (at most three rounds); an Explainer writes the coordinator's report and the exact changes against the previous version. All agents share one Meterless World Model, whose event history explains each re-plan. When the protocol becomes infeasible — blocking road T6 leaves critical communities needing 17,952 kg that the fording vehicles (13,800 kg) cannot carry — the plan is delivered as a best effort and escalated with that exact gap. Measured over 60 runs: 0 failures, one critic round per plan, 0 false critic blocks.

## Sponsor technology explanation

**Zetaris (data).** Zetaris is the agents' only data source. The scenario (communities, shelters, warehouses, inventory, road network, vehicles, field reports and the rainfall series) lives in our own Postgres, registered in Zetaris as the datasource `resq_pg` (`CREATE DATASOURCE` + `REGISTER DATASOURCE TABLES`, scripted in `scripts/register_zetaris.py`). The agents run Lightning SQL through Zetaris' REST API, one statement per request (`resq/tools/zetaris.py`): every scenario table, the field reports the Reconciler weighs and the 24-hour rainfall the Risk Analyst uses. The team reaches the Zetaris host over Tailscale. A `SAMPLE_MODE` runs the same SQL on a local copy so judges can run it without Zetaris.

**Meterless (engine + Nightshift).**
- **World Model engine:** the shared, event-sourced state of all six agents (`world_service/` runs the Meterless World Model reference behind a small HTTP API; `resq/world/` is the client). Scenario rows are entities; verified statuses, risk assessments, coordinator actions and every published plan are facts with provenance (source, agent, observation time, confidence, evidence ids). The "most recent observation wins" policy keeps a later-written but older report from undoing a coordinator's road block, and the event history is what the Explainer uses to answer "why did the plan change?". It also gives point-in-time state ("what did we believe at 10:00?") and an audit log (`python -m resq.world`). Conformance suite: **8/8 passing** (`cd world_service && npm run conformance`), also run in CI.
- **Nightshift:** the primary AI provider. `resq/llm.py` uses Nightshift's OpenAI-compatible Runtime with the `meterless-app` / `meterless-scope` headers, configured with `METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN` and `METERLESS_MODEL`; `python -m resq.llm --check` runs the connection, authorization, model-discovery and per-lane request checks. Two lanes: fast and deep.

**NVIDIA (Nemotron through Nightshift).** Both lanes are pinned to Nemotron models through Nightshift: `nvidia/nemotron-3.5-lightning-30b-a3b` on the fast lane (Reconciler deciding contested reports, Risk Analyst summary, Explainer report) and `nvidia/nemotron-3-ultra-550b-a55b` on the deep lane (Planner choosing delivery tiers under scarcity, Critic reviewing the reasons). Every model call is recorded with its model id in the JSONL trace. Nemotron's thinking mode is turned off per lane after measuring it (5× slower, one call in three over the 90 s timeout); both lanes run at temperature 0 for a rehearsable demo.

**Cursor (development).** The team developed RESQ AI in Cursor. `AGENTS.md` is the shared context file the coding agent reads before every task (rules, contracts between modules, status, decision log), which let three people and their agents work on separate branches against the same contracts; Claude Code and Codex, which the rules allow, used the same file.

- **Harry:** built the heavy test battery with its automatic quality checks and failure classification (`scripts/heavy_test.py`), then used its results to fix the agents — the Critic was rejecting correct plans because it could not see which communities a road block had left reachable only by fording vehicles, and both lanes moved to temperature 0 after measuring that the Planner's answers changed between runs. The agent also ran the model comparisons that decided the deep lane (thinking off, Nemotron 3 Ultra) and caught that the dashboard's live mode never started because the repo root was missing from `sys.path`.
- **[team]** Juan — one or two concrete things (e.g. Zetaris registration and the World Model service).
- **[team]** Chema — one or two concrete things (e.g. the dashboard and the validators).

**What was unique in our use of the sponsor technologies.**
- The World Model is the agents' only shared memory, not a cache next to it: re-plans, explanations and "what did we believe then?" all come from its event history and provenance.
- Zetaris serves every number the agents reason over, and the identical SQL also runs offline, so the agent code is the same with and without Zetaris.
- Nemotron is used only where judgment is needed (which report to believe, how to share scarce aid, whether a reason holds) and never for arithmetic; that split was decided from measured failures, not assumed.

## Pre-existing components (declare in the form)

- `smoke_test.py` — from the official hackathon Participant Setup Guide.
- `world_service/vendor/world-model/` — Meterless World Model reference implementation and conformance runner (Apache-2.0, unmodified, commit `1742dec`).
- `app/static/fonts/` — Barlow Condensed fonts (SIL Open Font License).
- Open-source libraries listed in `requirements.txt` and `world_service/package.json`.
- Rainfall snapshot from the Open-Meteo archive (CC BY 4.0), fetched during the build window.
- No product code from before the build window: the first commit is 23 October 2026, 08:47 UTC.

## How judges can run it

See the README section "For judges: three ways to run it": the dashboard's example mode runs offline in two minutes with no keys; the agents run on the sample data with one model key; the full stack needs Zetaris and Nightshift.

## Final checklist

| Item | Owner | Done |
| --- | --- | --- |
| Nightshift Console token renewed; `python -m resq.llm --check` passes with "Meterless Nightshift" | Harry | [x] 8/8 PASS, no WARN |
| `python scripts/run_demo.py` on Nightshift + Zetaris; `output_examples/` regenerated and committed | Harry | [x] PR #8, 17,952 kg |
| Nightshift console screenshots (resq-ai requests on Nemotron, no keys visible) in `docs/evidence/` | Harry | [x] PR #8 |
| Demo video 1–4 min: problem, plan, critic revision, block T6 → re-plan and escalation, "why", Zetaris + World Model + Nightshift/Nemotron shown | Harry | [ ] |
| Slide deck: problem and users, solution, agent architecture, stack, Zetaris and Meterless use and what was unique, screenshots, future work | Chema | [ ] |
| Cursor usage sentence per member (above) | All | [ ] |
| Clean-setup run following the README (path 1 and 2) | Chema | [ ] |
| Secret scan of the whole history (`git log --all -p` for keys and tokens) | Juan | [ ] |
| Repository made **public** | Juan | [ ] |
| HackOS form: track Reasoning Architecture, links, sponsor explanation, pre-existing components | Juan | [ ] |
| Submitted before 12:00 Guatemala (hard limit 17:45) | Juan | [ ] |
