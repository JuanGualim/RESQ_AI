# RESQ AI

**Multi-agent decision support for flood aid distribution.** Open Agent Hackathon 2026 · Track 3: Reasoning Architecture.

During a flood, field reports contradict each other and distribution plans go stale within minutes. RESQ AI helps a **municipal emergency coordinator** decide which communities to serve first, with which supplies, from which warehouse, by which vehicle and route. It reconciles contradictory reports, scores risk, plans under scarcity, has a critic check the plan, and re-plans when reality changes (for example, a road gets blocked), explaining **what changed and why**. When the protocol cannot be met, it says so and escalates to a human with the exact gap.

## How it works

```text
question / event ─► Intake ─► Reconciler ─► Risk Analyst ─► Planner ⇄ Critic (max 3 rounds) ─► Explainer
                                  │               │              │          │                     │
                               verified        risk and       tiers +    hard rules +          report +
                                facts           needs         packing    model review          exact diff
                                  └──────────────── World Model (Meterless) ─────────────────────┘
```

- **The model decides and explains; code computes.** Routes (networkx), risk arithmetic, vehicle packing and hard validations are deterministic and tested. The model decides which contradictory report to believe, how much each community receives, whether a plan's reasoning holds, and writes the report.
- **Critique and revision:** the Critic runs the protocol's hard rules in code and a model review of the reasons; rejected plans go back to the Planner with concrete feedback.
- **Escalation:** if the protocol minimum is infeasible (e.g. after blocking segment T6, critical communities need 17,952 kg of water and food but the fording vehicles carry 13,800 kg), the plan is marked `escalated` with the reason.
- **Traceability:** every step writes a JSONL trace line; every fact in the World Model carries its provenance and evidence (report ids).

Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · Domain rules: [`docs/protocol.md`](docs/protocol.md) · Scenario data: [`data/README.md`](data/README.md) · Example outputs: [`output_examples/`](output_examples/)

## Sponsor technology: where it is used

| Sponsor | Where | How |
| --- | --- | --- |
| **Zetaris** | `resq/tools/zetaris.py` | The agents' only data source: every scenario table is read with Lightning SQL over Zetaris' REST API |
| **Meterless World Model** | `world_service/`, `resq/world/` | Shared, event-sourced state of all agents: scenario entities, verified facts, risk assessments, coordinator events and published plans. The Explainer reads its history to explain re-plans; `python -m resq.world` shows timelines, point-in-time state and the audit log. Conformance suite: 8/8 |
| **Meterless Nightshift** | `resq/llm.py` | Primary model provider (OpenAI-compatible API, `meterless-app` headers) |
| **NVIDIA Nemotron** | `resq/llm.py` lanes | `nvidia/nemotron-3.5-lightning-30b-a3b` on the fast lane; deep lane configurable |
| **Cursor** | development | IDE used by the team (with Claude Code and Codex) |

## Quick start (no services: `SAMPLE_MODE`)

Requirements: Python 3.12+, Node.js 20+, a model endpoint (Nightshift, or an NVIDIA API key for development).

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                   # set MODEL_* and SAMPLE_MODE=true
pytest                                 # 166 tests, offline
```

Start the World Model service in its own terminal:

```bash
cd world_service
npm install
npm run conformance
npm start
```

Then, with `WORLD_MODEL_URL=http://127.0.0.1:4380` in `.env`:

```bash
python -m resq.run --reset
python -m resq.run --question "How should we distribute aid right now?"
python -m resq.run --event block:T6
python -m resq.run --question "Why did the plan change?"
```

Coordinator dashboard (example mode works offline from `output_examples/`; live mode calls `resq.run.execute()`):

```bash
streamlit run app/streamlit_app.py
```

Full mode reads the same tables from Zetaris (`SAMPLE_MODE=false`, `ZETARIS_*` variables): the scenario lives in our own Postgres (`docker compose up -d`, `python scripts/load_postgres.py`), registered in Zetaris as the datasource `resq_pg` (`python scripts/register_zetaris.py`). See [`docs/TEAM_SETUP.md`](docs/TEAM_SETUP.md).

## Data

All scenario data is synthetic (fictional municipality, no real people). Rainfall is a real public snapshot from the Open-Meteo archive (Hurricane Eta, November 2020). Contradictions are seeded in the data, never in the code.

## Prior components

- `smoke_test.py` comes from the official hackathon guide.
- `world_service/vendor/world-model/` is the Meterless World Model reference implementation and conformance runner (Apache-2.0, unmodified), vendored as Meterless' own starter template does.

## Status

Work in progress for the hackathon (deadline Oct 27, 2026). Current status and next steps: [`AGENTS.md`](AGENTS.md) §8–9.
