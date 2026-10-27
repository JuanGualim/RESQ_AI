# RESQ AI

**Multi-agent decision support for flood aid distribution.** Open Agent Hackathon 2026 · Track 3: Reasoning Architecture.

> RESQ AI helps a **municipal emergency coordinator** decide how to distribute scarce aid during a flood, by reconciling contradictory field reports, scoring each community's risk under a written protocol and planning deliveries that a critic agent checks, using scenario data served by **Zetaris**, and producing a **versioned distribution plan** that is re-planned when a road is blocked, with **what changed and why**, or escalated to a human when the protocol can no longer be met.

During a flood, field reports contradict each other ("T7 open" in the official bulletin, "60 cm of water" from two brigades), stock and vehicles do not cover every need, and a plan goes stale as soon as a road closes. RESQ AI turns that into a decision the coordinator can act on and defend.

## How it works

```text
question / event ─► Intake ─► Reconciler ─► Risk Analyst ─► Planner ⇄ Critic (max 3 rounds) ─► Explainer
                                  │               │              │          │                     │
                               verified        risk and       tiers +    hard rules +          report +
                                facts           needs         packing    model review          exact diff
                                  └──────────── Meterless World Model (shared state) ────────────┘
```

- **The model decides and explains; code computes.** Nemotron decides which contradictory report to believe, how much each community receives (a delivery tier) and whether a plan's reasoning holds, and writes the report. Routes (networkx), risk arithmetic, vehicle packing and the protocol's hard rules are deterministic, tested code.
- **Critique and revision:** the Critic runs the hard rules in code plus a model review of the reasons; a rejected plan goes back to the Planner with concrete feedback.
- **Escalation:** when the protocol minimum is infeasible (after blocking segment T6, critical communities need **17,952 kg** of water and food but the fording vehicles carry **13,800 kg**), the plan is delivered as a best effort and marked `escalated` with that reason.
- **Recovery:** if Zetaris or the World Model is unreachable, a run ends escalated with a readable reason instead of a crash.
- **Traceability:** every agent step writes a JSONL trace line; every fact in the World Model carries its provenance (source, agent, observation time, confidence, report ids).

Results measured with `scripts/heavy_test.py` (4 scenarios × 5 runs): **60 turns, 0 failures, 1.0 critic rounds per plan, 0 false critic blocks**, 29–50 s per turn ([`docs/test_results/`](docs/test_results/)).

More: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · rules [`docs/protocol.md`](docs/protocol.md) · data [`data/README.md`](data/README.md) · sample inputs [`input_examples/`](input_examples/) · sample outputs and traces [`output_examples/`](output_examples/)

## Sponsor technology

| Sponsor | Where | What it does in RESQ AI |
| --- | --- | --- |
| **Zetaris** | `resq/tools/zetaris.py`, `scripts/register_zetaris.py` | The agents' only data source. The scenario lives in our own Postgres, registered in Zetaris as the datasource `resq_pg`; agents run Lightning SQL over Zetaris' REST API (scenario tables, field reports, 24 h rainfall) |
| **Meterless World Model** (engine) | `world_service/`, `resq/world/` | The shared, event-sourced state of every agent: scenario entities, verified facts with provenance, risk assessments, coordinator events and every published plan. "Most recent observation wins" keeps a later-written old report from undoing a coordinator block; its history explains each re-plan. Conformance suite **8/8** (`npm run conformance`) |
| **Meterless Nightshift** | `resq/llm.py`, `resq/config.py` | Primary model provider: OpenAI-compatible Runtime with `meterless-app` / `meterless-scope` headers, configured with `METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN`, `METERLESS_MODEL`. `python -m resq.llm --check` runs connection, authorization, model discovery and one request per lane |
| **NVIDIA Nemotron** | lanes in `resq/llm.py` | Served through Nightshift: fast lane `nvidia/nemotron-3.5-lightning-30b-a3b` (Reconciler, Risk Analyst, Explainer), deep lane `nvidia/nemotron-3-ultra-550b-a55b` (Planner, Critic). The model id of every call is recorded in the trace |
| **Cursor** | development | The team built RESQ AI in Cursor's Agent chat. `AGENTS.md` is the shared context file the coding agent reads first (contracts, rules, status), so three people and their agents could work on separate branches against the same contracts |

**What is unique in how we use them:** the World Model is not a cache but the agents' only shared memory, and its event history is what makes "why did the plan change?" answerable. Zetaris serves every number the agents reason over, so the same SQL runs on Zetaris and, in `SAMPLE_MODE`, on a local copy. Nemotron is used where judgment is needed (contested reports, tiers under scarcity, review of reasons), never for arithmetic.

## For judges: three ways to run it

**1. Look at it in two minutes (no keys, no services).** The dashboard has an example mode that replays a real run from `output_examples/`.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app/streamlit_app.py     # example mode: baseline plan, T6 blocked, trace, map
pytest                                 # 182 tests, offline, no keys
```

**2. Run the agents on the sample data (one model key).** Copy `.env.example` to `.env`, set `SAMPLE_MODE=true` and your Nightshift Console values in `METERLESS_BASE_URL` / `METERLESS_RUNTIME_TOKEN` and in `MODEL_BASE_URL` / `MODEL_API_KEY` (read by `smoke_test.py`; for development they can point at direct NVIDIA instead). Both lanes are pinned to Nemotron. Check the provider, then run:

```bash
python -m resq.llm --check
python -m resq.run --reset
python -m resq.run --question "How should we distribute aid right now?"
python -m resq.run --event block:T6
python -m resq.run --question "Why did the plan change?"
```

Without `WORLD_MODEL_URL` the agents use an in-memory fallback of the World Model. To run on the real engine (Node.js 20+), start it in a second terminal and set `WORLD_MODEL_URL=http://127.0.0.1:4380`:

```bash
cd world_service && npm install && npm run conformance && npm start
```

**3. Full stack.** Zetaris running locally (`SAMPLE_MODE=false`, `ZETARIS_*` in `.env`): `docker compose up -d`, `python scripts/load_postgres.py`, `python scripts/register_zetaris.py`. Then `python scripts/run_demo.py` runs baseline → block T6 → why and writes the outputs. Team setup, Tailscale and Windows notes: [`docs/TEAM_SETUP.md`](docs/TEAM_SETUP.md), [`docs/windows_install_notes.md`](docs/windows_install_notes.md).

Inspect the shared state after a run: `python -m resq.world summary`, `timeline T7`, `state --at 2020-11-05T10:00`, `audit`.

## Data

All scenario data is **synthetic**: a fictional riverside municipality, 14 communities, 21 road segments, 6 vehicles and 30 field reports with seeded contradictions; no real people. Rainfall is a real public snapshot from the Open-Meteo historical weather archive (Hurricane Eta, November 2020), **Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed CC BY 4.0**. Contradictions are seeded in the data, never in the code. Details, licence and how to regenerate: [`data/README.md`](data/README.md).

## Limitations

- A hackathon prototype on a fictional scenario; the protocol (`P1`–`P8`) is simplified, not an official emergency standard. It supports a coordinator's decision and escalates; it does not replace one.
- Nemotron is a mixture-of-experts model served in batches, so identical requests can return slightly different tiers even at temperature 0. Everything code computes (critical communities, feasibility, the escalation and its gap) is stable.
- Distances and travel are schematic (graph distances), not live GPS routing.

## Pre-existing and third-party components

- `smoke_test.py` comes from the official hackathon setup guide.
- `world_service/vendor/world-model/` is the Meterless World Model reference implementation and conformance runner (Apache-2.0, unmodified, commit `1742dec`), vendored the way Meterless' own starter template vendors its engines.
- `app/static/fonts/` are Barlow Condensed fonts (SIL Open Font License, `OFL.txt`).
- Open-source libraries from `requirements.txt` and `world_service/package.json`.
- Everything else was written during the build window (first commit 23 October 2026, 08:47 UTC).

## Team

Juan (data, Zetaris, World Model, integration) · Harry (models, Nightshift, Planner / Critic / Explainer, testing, demo) · Chema (routing, validators, dashboard, deck). Project context for people and coding agents: [`AGENTS.md`](AGENTS.md).
