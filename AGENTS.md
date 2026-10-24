# AGENTS.md — RESQ AI

> **Read this whole file before touching code.** It is the project's source of truth for people and AI agents (Cursor, Claude Code, Codex). At the end of every work session, update **§8 Current status**, **§9 Next steps** and, if you decided something, **§10 Decision log**.

Last updated: 2026-10-24 (GT) · by: Juan (with Claude Code): repo skeleton, `resq/config.py`, data generator and `data/sample/`

---

## 1. The project in 30 seconds

**RESQ AI** is a multi-agent system that helps a **municipal emergency coordinator** decide how to distribute aid during a **flood**. It combines data on communities, shelters, warehouses, roads, vehicles, rainfall and contradictory field reports; prioritizes using protocol rules; and delivers a **versioned distribution plan** that is re-planned when reality changes (e.g. a road segment gets blocked), explaining **what changed and why**.

- Event: **Open Agent Hackathon 2026** · **Track 3: Reasoning Architecture**
- Deadline: **Tuesday 27-Oct-2026, 17:45 Guatemala time** (23:45 UTC). Internal target: Tuesday 12:00.
- Team (full split in `docs/PLAN.md` §3):
  - **Juan:** Linux, Zetaris host. Data, World Model, Reconciler and Risk Analyst; integration and submission. Cannot run Nightshift.
  - **Harry:** Windows, powerful machine, Nightshift host. `llm.py`, graph, Planner, Critic and Explainer; heavy testing, demo and video.
  - **Chema:** modest machine. Routing, validators, Intake, UI on sample data, protocol and deck; works in `SAMPLE_MODE`.
- Full plan: `docs/PLAN.md` · Environment setup: `docs/TEAM_SETUP.md`

## 2. Non-negotiable rules (breaking one gets us disqualified or costs points)

1. **Zetaris is the agent's only data source.** Every scenario datum is read with SQL through Zetaris (`resq/tools/zetaris.py`). The exception is `SAMPLE_MODE=true` (local copy for judges and for development without services).
2. **Meterless Nightshift is the primary AI provider.** Every model call goes through `resq/llm.py`, which uses Nightshift's OpenAI-compatible API. Direct NVIDIA is only allowed in development, by changing `.env`; never as the default.
3. **At least one Meterless Engine actually working:** we use **World Model** as the agents' shared state, with its conformance suite passing. Mentioning or installing it without using it does not count.
4. **Development in Cursor** (Claude Code and Codex are also allowed).
5. **Secrets only in `.env`** (ignored by git). The repo holds `.env.example` with fake values. Never print, log or hardcode keys or tokens.
6. **Nothing hardcoded in the demo.** Results come from the data and the agents' reasoning. Contradictions are seeded in the data, never in the code.
7. **Synthetic data.** No real personal data. The municipality is fictional; rainfall comes from Open-Meteo (public, no key).
8. **A real multi-agent system**, not a linear pipeline: there must be critique, revision, bounded retries, branching and escalation, with a visible trace.
9. **Everything in English.** This is an international event and the judges review the repo: code, identifiers, comments, docstrings, logs, UI text, agent prompts and outputs, docs, commit messages and PRs are written in English. Team chat can stay in Spanish; anything that lands in the repo or the demo is English.

## 3. Architecture

```text
UI (Streamlit) ── question / event ("block segment T7")
  ▼
Intake ─ classifies: situation | plan | event | why
  ▼
Reconciler ─ contradictory reports → facts + confidence ─► World Model
  ▼
Risk Analyst ─ SQL (Zetaris) → risk per community ─► World Model
  ▼
Planner ─ rules + best_route + capacities → Plan vN
  ▼
Critic ─ code validators + LLM
  │  ✗ → back to the Planner with feedback (max. 3 rounds)
  │  ✗✗ → escalated=True: "requires a human decision"
  ✓
Explainer ─ final plan + changes vs. previous version (World Model history)

Shared: Zetaris · World Model · Nightshift→Nemotron · JSONL trace in logs/
```

**Principle: the LLM decides and explains; the code computes.** Routes, capacities, inventory and hard validations are deterministic, tested functions. Agents reason over their results.

| Agent | Module | Lane | Tools | Output |
| --- | --- | --- | --- | --- |
| Intake | `intake` | fast | rules (Scout Intent optional) | request type |
| Reconciler | `reconciler` | fast | `run_sql` | verified-fact events → World Model |
| Risk Analyst | `risk_analyst` | fast | `run_sql` | risk per community → World Model |
| Planner | `planner` | deep | `best_route`, inventory | `Plan` |
| Critic | `critic` | deep | `validators.*` | approved / feedback / escalated |
| Explainer | `explainer` | fast | `world.history()` | final report |

Framework: **LangGraph** (Python). Graph state = `ResqState` (pydantic) + World Model as shared domain state.

## 4. Stack and services

| Piece | Detail |
| --- | --- |
| Python | 3.12 recommended (Juan uses 3.14 on Linux; if a dependency fails, use 3.12) |
| Agents | LangGraph, `openai` (compatible client), pydantic |
| Routing | networkx over the `road_segments` table |
| UI | Streamlit |
| Zetaris | Runs on Juan's laptop (Docker). UI `:3000`, REST `:8888/api/v1.0`. The team connects through Tailscale |
| Nightshift | Runs on Harry's Windows machine (Juan cannot install it on Linux). Base URL `:8088/v1`. Lanes: fast = `nvidia/nemotron-3.5-lightning-30b-a3b`; deep = Nemotron super (to be confirmed) |
| World Model | Meterless engine (TypeScript). Recommended plan: Node service + Python client in `resq/world/` (see `docs/PLAN.md` R1). Spec and conformance: https://github.com/Meterless/Meterless/tree/main/engines/world-model |
| Meterless prompts | https://meterless.ai/engines.html (IMPLEMENT → *Keep parallel agents in sync*; POWER → *Add Meterless as a provider*) |

### Talking to Zetaris

- `POST {ZETARIS_REST_URL}/sql-editor/sqls/run`
- Headers: `Authorization: Bearer {ZETARIS_API_KEY}`, `X-Org-ID: {ZETARIS_ORG_ID}`, `X-Request-ID: <new uuid4>`
- Body: `{"queryId": "<uuid4>", "sql": "<ONE statement>", "source": "SqlEditor", "limit": N}` → response with `data` (rows)
- **Lightning SQL** dialect. **One statement per request.** Reference: http://localhost:8888/redoc/index.html and https://github.com/zetaris/getting-started (its `AGENTS.md`)
- Zetaris **does not read files from the laptop**: scenario data lives in our own Postgres registered as a data source.
- Never use port 8889 (internal).

### Talking to Nightshift

- OpenAI-compatible API: `GET /v1/models`, `POST /v1/chat/completions`
- Headers: `Authorization: Bearer {METERLESS_RUNTIME_TOKEN}`, `meterless-app: resq-ai`, `meterless-scope: user`
- `meterless/auto` may route to a non-NVIDIA model: for the demo and the NVIDIA prize, **pin a lane to Nemotron**.
- Known errors: `404 page not found` = URL without `/v1` or a non-chat model (`rerank`, `embed`); `Function … Not found for account` = model with no endpoint for the account.

## 5. Repo structure (target)

```text
RESQ_AI/
├── AGENTS.md              # this file (living context)
├── CLAUDE.md              # points to AGENTS.md (local only, gitignored)
├── README.md              # install, usage, dependencies (for judges)
├── requirements.txt
├── .env.example           # no secrets
├── smoke_test.py          # checks Zetaris + model (from the official guide)
├── docs/
│   ├── PLAN.md            # phased plan
│   ├── TEAM_SETUP.md      # environment guide
│   └── protocol.md        # priority rules (domain knowledge)
├── resq/
│   ├── config.py          # reads .env, SAMPLE_MODE
│   ├── llm.py             # chat(messages, lane, tools) → Nightshift
│   ├── schemas.py         # Assignment, Plan, Event, ResqState
│   ├── graph.py           # LangGraph graph
│   ├── agents/            # intake, reconciler, risk_analyst, planner, critic, explainer
│   ├── tools/
│   │   ├── zetaris.py     # run_sql
│   │   ├── routing.py     # best_route
│   │   └── validators.py  # the critic's hard rules
│   ├── world/             # World Model integration
│   └── run.py             # CLI: python -m resq.run --question "..."
├── app/streamlit_app.py   # UI
├── scripts/generate_data.py   # synthetic data (fixed seed)
├── data/sample/ + data/README.md
├── input_examples/  output_examples/
├── logs/                  # JSONL traces (.log files are not committed)
└── tests/
```

## 6. Contracts between modules

Changing a contract = tell the group + record it in §10.

```python
# resq/tools/zetaris.py  (Juan)
def run_sql(sql: str, limit: int = 500) -> list[dict]: ...   # one statement; raises ZetarisError

# resq/llm.py  (Harry)
def chat(messages: list[dict], lane: str = "fast", tools: list | None = None) -> dict: ...  # "fast" | "deep"

# resq/world/  (Juan)
def get_state() -> dict: ...                 # communities, road segments, shelters with their current status
def apply_event(event: dict) -> None: ...    # {"type": "segment_blocked", "id": "T7", "source": "...", "ts": "..."}
def history() -> list[dict]: ...             # events in order

# resq/tools/routing.py  (Chema)
def best_route(origin: str, destination: str, state: dict, vehicle_id: str) -> "Route | None": ...

# resq/tools/validators.py  (Chema)
def validate_plan(plan: Plan, state: dict) -> list[str]: ...  # empty list = no violations; each message cites IDs

# resq/schemas.py  (everyone; Harry creates it)
class Assignment(BaseModel): community_id: str; origin_id: str; resource: str; quantity: int; vehicle_id: str; route: list[str]; priority: int; reason: str; evidence: list[str]
class Plan(BaseModel): version: int; assignments: list[Assignment]; unserved: list[str]; risks: list[str]; confidence: float; escalated: bool; changes_vs_previous: list[str]

# Graph nodes (each owner implements theirs; Harry defines the shape)
def node_<agent>(state: ResqState) -> dict: ...   # returns only the fields it updates

# resq/run.py  (Harry) — what Chema's UI calls
def execute(question: str, event: dict | None = None) -> dict: ...  # {"plan": Plan, "trace": list[dict], "escalated": bool}
```

### Scenario data (tables in Zetaris)

`communities`(id, name, population, pct_children, pct_elderly, vulnerability 1–5, elevation_m, lat, lon, road_node) · `shelters`(id, name, capacity, current_occupancy, road_node) · `warehouses`(id, name, road_node) · `inventory`(warehouse_id, resource, quantity, unit_weight_kg) · `road_segments`(id, origin, destination, distance_km, surface, official_status) · `vehicles`(id, type, capacity_kg, can_ford, warehouse_id) · `field_reports`(id, timestamp, source: official|brigade|social_media, object_type, object_id, reported_status, detail) · `rainfall` (Open-Meteo REST: datetime, precipitation_mm).

Size: 12–15 communities, 3–4 shelters, 2 warehouses, ~20 road segments, 5–8 vehicles, ~30 reports. Current sample: 14 · 4 · 2 · 21 · 6 · 30, plus 107 hourly rainfall rows. Status vocabularies, scenario story and the list of seeded contradictions: `data/README.md`.

## 7. Conventions for AI agents and people

- **Language:** English for everything in the repo and the demo (rule 9 of §2). Identifiers in `snake_case`/`PascalCase` English; no Spanish names in new code.
- **Small changes** focused on the requested task; do not rewrite another member's modules without telling them.
- **Do not invent APIs** for Zetaris or Meterless: check the sources in §4. If unsure, say so and leave a `TODO(verify)`.
- **Models:** only through `resq/llm.py`. No other file creates OpenAI clients.
- **Data:** only through `resq/tools/zetaris.py` (or `SAMPLE_MODE`).
- **Trace:** every agent step writes one JSONL line in `logs/` (`ts, run_id, agent, input_summary, output_summary, lane, model, duration_ms, iteration`). Never include secrets.
- **Limits:** timeouts on every external call (Zetaris 60 s, model 90 s); max. 3 critic rounds; max. 2 retries.
- **Tests:** `pytest` in `tests/` for deterministic tools (routing, validators). Run `python smoke_test.py` and `pytest` before opening a PR.
- **Git:** branches `feat/<area>-<topic>`; small commits with English messages; PR to `main`; Juan reviews. Never `git add .env`.
- **When closing a session:** update §8, §9 and §10 of this file.

### How to run

```bash
# Linux/macOS
python -m venv .venv && source .venv/bin/activate
# Windows: py -3.12 -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # then fill in real values
python smoke_test.py        # 3 PASS expected
python scripts/generate_data.py   # rebuild data/sample/ (add --fetch-rainfall to refresh rainfall.csv)
pytest                      # unit tests
# (once they exist)
python -m resq.run --question "How should we distribute aid right now?"
streamlit run app/streamlit_app.py
```

### Environment variables

| Variable | Use |
| --- | --- |
| `ZETARIS_BASE_URL` | Zetaris UI (smoke test) |
| `ZETARIS_REST_URL`, `ZETARIS_ORG_ID`, `ZETARIS_API_KEY` | Zetaris REST API |
| `METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN`, `METERLESS_MODEL` | Nightshift (primary provider) |
| `MODEL_BASE_URL`, `MODEL_API_KEY`, `NEMOTRON_MODEL` | Active model (Nightshift by default; direct NVIDIA only in development) |
| `LANE_FAST_MODEL`, `LANE_DEEP_MODEL` | Model per lane (to be defined) |
| `SAMPLE_MODE` | `true` = use `data/sample/` without Zetaris |
| `WORLD_MODEL_URL` | (proposal, confirmed with R1) URL of the local World Model service |

---

## 8. Current status

**Current phase: 0, Kickoff — behind schedule** (target was Friday 23, 14:00; the Friday 18:00/20:00 Phase 1 milestones were also missed). Harry and Chema cannot work yet, so Juan moves forward alone on everything that does not need Nightshift.

Done:
- [x] Track 3 chosen; RESQ AI idea defined
- [x] Zetaris installed and running on Juan's laptop (`verify.sh` OK, API token created, REST tested)
- [x] Cursor working (Juan)
- [x] `smoke_test.py` → 3 PASS on Juan's Linux, with direct NVIDIA and `nvidia/nemotron-3.5-lightning-30b-a3b`
- [x] Repo `JuanGualim/RESQ_AI` with initial commits (`smoke_test.py`, `.gitignore`, `.env.example`, `requirements.txt`, `AGENTS.md`, `docs/PLAN.md`)
- [x] `docs/PLAN.md` v2: split by machine (Juan / Harry / Chema), timed milestones, stubs to avoid blocking, new contracts, risks R9–R11
- [x] Project language switched to English: `AGENTS.md`, `docs/PLAN.md`, `.env.example` and `smoke_test.py` translated; contracts and table names renamed (§6)
- [x] `smoke_test.py` still gives 3 PASS after the translation (2026-10-24)
- [x] Repo skeleton from §5 (`resq/` packages, `app/`, `logs/`, examples folders, `pytest.ini`)
- [x] `resq/config.py`: typed settings from `.env`, `SAMPLE_MODE`, lane fallbacks, secrets hidden from `repr` + `tests/test_config.py`
- [x] `scripts/generate_data.py` (seed `20201105`) → `data/sample/` (8 CSVs) + `data/README.md` + `tests/test_generate_data.py`; rainfall = real Open-Meteo archive of Hurricane Eta up to the decision time 2020-11-05 10:00
- [x] `pytest`: 25 passed (2026-10-24)

Pending / blocked:
- [ ] `docs/TEAM_SETUP.md` is referenced but **does not exist**
- [ ] No agent code yet: `schemas.py`, `llm.py`, `zetaris.py`, `world/`, routing, validators and agents are still missing
- [ ] Scenario data not yet in Postgres / Zetaris (only `data/sample/` CSVs)
- [ ] Nightshift installed on Harry's Windows machine and exposed over Tailscale (blocked: Harry)
- [ ] Tailscale between the 3 machines; Zetaris and Nightshift reachable
- [ ] Harry and Chema setup (smoke test on their machines) (blocked: Harry, Chema)
- [ ] Decide the World Model integration (R1). Recommended: Node service + Python client
- [ ] `CLAUDE.md` is in `.gitignore`, so it is not committed even though §5 lists it. Decide whether to version it

## 9. Next steps (in order)

Juan, solo, while Harry and Chema are unavailable (all of this works with direct NVIDIA or no model at all):

1. Share `data/sample/` and `data/README.md` with the team (push) so Chema can start `best_route` and validators on it.
2. `docs/TEAM_SETUP.md`; invite collaborators on GitHub.
3. Unblocking stubs for Harry's contracts, telling him first: `resq/schemas.py` (§6) and a minimal `resq/llm.py` that already works with direct NVIDIA.
4. World Model *90-second proof* on Linux → close R1 → in-memory stub of `resq/world/` with the real contract.
5. Postgres in Docker + register it in Zetaris + `run_sql` + 10 key queries tested + Open-Meteo `rainfall` table.
6. Real World Model (Node service) + Python client + **conformance green**.
7. Reconciler and Risk Analyst agents on `SAMPLE_MODE` first, then on real SQL.
8. Install Tailscale and expose Zetaris, ready for when the others join.

When Harry and Chema are back: 45-minute call to confirm the English contracts (§6), then pick up their Phase 1 items from `docs/PLAN.md` §4.

## 10. Decision log

| Date (GT) | Decision | Why |
| --- | --- | --- |
| 2026-10-22 | Track 3: Reasoning Architecture | The output is a decision that gets re-planned with new state |
| 2026-10-23 | Zetaris on Juan's Linux laptop; Nightshift on Harry's Windows machine; Tailscale network | Nightshift has no Linux version; Zetaris needs 16 GB; Harry has the best machine |
| 2026-10-23 | Development with direct NVIDIA allowed; Nightshift mandatory for the demo and defaults | Don't block anyone if the Nightshift host is unavailable |
| 2026-10-23 | Main engine: World Model | Shared state + event history = explanation of re-plans |
| 2026-10-23 | Routing and validations in deterministic code; the LLM decides and explains | Reliability and reproducibility in front of judges |
| 2026-10-23 | Scenario data in our own Postgres registered in Zetaris | Zetaris does not read local CSVs |
| 2026-10-23 | Split by machine: Juan = data + World Model + Reconciler/Risk Analyst; Harry = Nightshift + `llm.py`/graph/Planner/Critic/Explainer + heavy testing + demo; Chema = routing, validators, Intake, UI, protocol, deck | Juan cannot run Nightshift; Chema's machine is modest; Harry has a powerful Windows machine |
| 2026-10-23 | New contracts: `validate_plan(plan, state) -> list[str]`, `node_<agent>(state) -> dict`, `run.execute(question, event) -> dict` | The UI and the Critic needed a fixed interface to work in parallel |
| 2026-10-23 | Each owner publishes a stub with the contract before the real version | Avoid blocking in Phase 1 |
| 2026-10-24 | `inventory` gets a `unit_weight_kg` column | The critic must check vehicle `capacity_kg`, which needs the weight per unit of each resource |
| 2026-10-24 | Scenario replays Hurricane Eta: rainfall from the Open-Meteo archive (Nov 1–5, 2020, at 15.47, -88.84), decision time 2020-11-05 10:00 local; field reports dated that morning | Real public rainfall that is reproducible (archive, not forecast) and heavy enough to justify the flood |
| 2026-10-24 | Segment ids keep the `T` prefix (`T1`–`T21`); nodes `N01`–`N16`; segments are undirected | Matches the "block segment T7" demo wording already in the docs |
| 2026-10-24 | **Everything in the repo and demo is in English** (code, identifiers, docs, prompts, UI, commits). Contracts and tables renamed: `Asignacion`→`Assignment`, `validar_plan`→`validate_plan`, `ejecutar`→`execute`, `comunidades`→`communities`, `tramos`→`road_segments`, etc. (§6) | International event with international judges; renaming now costs nothing because no code exists yet |