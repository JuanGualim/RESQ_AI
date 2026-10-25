# AGENTS.md — RESQ AI

> **Read this whole file before touching code.** It is the project's source of truth for people and AI agents (Cursor, Claude Code, Codex). At the end of every work session, update **§8 Current status**, **§9 Next steps** and, if you decided something, **§10 Decision log**.

Last updated: 2026-10-25 (GT) · by: Juan (with Claude Code): scenario in Postgres, registered in Zetaris as `resq_pg`; demo runs on Zetaris data; Tailscale

---

## 1. The project in 30 seconds

**RESQ AI** is a multi-agent system that helps a **municipal emergency coordinator** decide how to distribute aid during a **flood**. It combines data on communities, shelters, warehouses, roads, vehicles, rainfall and contradictory field reports; prioritizes using protocol rules; and delivers a **versioned distribution plan** that is re-planned when reality changes (e.g. a road segment gets blocked), explaining **what changed and why**.

- Event: **Open Agent Hackathon 2026** · **Track 3: Reasoning Architecture**
- Deadline: **Tuesday 27-Oct-2026, 17:45 Guatemala time** (23:45 UTC). Internal target: Tuesday 12:00.
- Team (full split in `docs/PLAN.md` §3):
  - **Juan:** Linux, Zetaris host. Data, World Model, Reconciler and Risk Analyst; integration and submission. Cannot run Nightshift.
  - **Harry:** Windows, powerful machine, Nightshift host. `llm.py`, graph, Planner, Critic and Explainer; heavy testing, demo and video.
  - **Chema:** modest machine. Routing, validators, Intake, UI on sample data, protocol and deck; works in `SAMPLE_MODE`.
  - While Harry and Chema were unavailable (Oct 24), Juan wrote **first working versions of every module**, including theirs. Owners keep ownership: review, test and improve your modules; do not start from scratch.
- Full plan: `docs/PLAN.md` · Environment setup: `docs/TEAM_SETUP.md` · Domain rules: `docs/protocol.md` · Data: `data/README.md`

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
CLI / UI ── question or coordinator event ("block:T6")
  ▼
Intake (rules) ─ classifies: situation | plan | event | why; stores events in the World Model
  ├─ why ─────────────────────────────────────────────────────────────► Explainer
  ▼
Reconciler ─ P1 scoring in code + model on contested objects → verified facts ─► World Model
  ▼
Risk Analyst ─ P3 risk index + P4 needs in code (SQL + routing) + model summary ─► World Model
  ├─ situation ───────────────────────────────────────────────────────► Explainer
  ▼
Planner (model) ─ delivery tier per community (P4.1)
  │   code: order by risk, critical minimum first (P5.2), pack vehicles/routes (P6)
  ▼
Critic ─ validate_plan (code) + feasibility check + one model review of reasons
  │  ✗ → back to the Planner with feedback (max. 3 rounds)
  │  infeasible / still rejected / low confidence → escalated = True
  ✓
Explainer ─ exact diff + causing events (code) + report (model) ─► plan_published ─► World Model

Shared: Zetaris (SQL) · World Model service (Meterless reference) · Nightshift→Nemotron · JSONL trace in logs/
```

**Principle: the LLM decides and explains; the code computes.** Routes, capacities, inventory, risk arithmetic, packing and hard validations are deterministic, tested functions. The model makes the judgment calls (which report to believe, how much each community gets, whether a reason holds) and explains them.

| Agent | Module | Lane | Code part | Model part | Writes |
| --- | --- | --- | --- | --- | --- |
| Intake | `agents/intake.py` | rules | classify, apply coordinator events | — | event → World Model |
| Reconciler | `agents/reconciler.py` | fast | P1 scores per reported status | decides contested objects, with reason | `*_status_verified` facts |
| Risk Analyst | `agents/risk_analyst.py` | fast | P3 index, P4 needs, reachability | situation summary | `community_risk_assessed` facts |
| Planner | `agents/planner.py` | deep | risk order, P5.2 minimum first, `packing.pack` | tier per community + reason | `Plan` |
| Critic | `agents/critic.py` | deep | `validate_plan`, `critical_minimum_gaps` | review of reasons (can send back once) | `CriticReview`, escalation |
| Explainer | `agents/explainer.py` | fast | `diff_plans`, change events, table | coordinator report | `plan_published` |

Framework: **LangGraph** (`resq/graph.py`). Graph state = `ResqState` (pydantic); domain state = World Model.

### Model notes (important)

- **Nemotron 3.5 thinks by default.** With thinking on, a plan request spends the whole token budget reasoning and returns empty content (seen with 16k tokens), or takes longer than the 90 s timeout. `llm.py` sends `chat_template_kwargs.enable_thinking=false` on the fast lane, and on the deep lane unless `LANE_DEEP_THINKING=true`. TODO(verify): that Nightshift forwards `chat_template_kwargs`.
- The fast model is weak at arithmetic over continuous numbers (it invented decreasing coverages), so the Planner chooses **discrete tiers** and code does the math.
- A full run takes ~40–60 s on direct NVIDIA (each model call 2–12 s).

## 4. Stack and services

| Piece | Detail |
| --- | --- |
| Python | 3.12 recommended (Juan uses 3.14 on Linux; everything works there) |
| Agents | LangGraph, `openai` (compatible client), pydantic |
| Routing | networkx over `road_segments` (`tools/routing.py`) |
| UI | Streamlit (not built yet) |
| Zetaris | Runs on Juan's laptop (Docker). UI `:3000`, REST `:8888/api/v1.0`. The team connects through Tailscale. Responses: `{"headers": [...], "data": [[...]]}` with **every value as text** (`run_sql` parses numbers) |
| Nightshift | Runs on Harry's Windows machine. Base URL `:8088/v1`. Lanes: fast = `nvidia/nemotron-3.5-lightning-30b-a3b`; deep = Nemotron super (to be confirmed) |
| World Model | `world_service/`: Node HTTP service over the **vendored Meterless World Model reference** (`world_service/vendor/world-model`, Apache-2.0, commit `1742dec`). Conformance 8/8. Python client in `resq/world/`; in-memory fallback when `WORLD_MODEL_URL` is empty (tests and dev only) |
| Meterless prompts | https://meterless.ai/engines.html (IMPLEMENT → *Keep parallel agents in sync*; POWER → *Add Meterless as a provider*) |

### Talking to Zetaris

- `POST {ZETARIS_REST_URL}/sql-editor/sqls/run`
- Headers: `Authorization: Bearer {ZETARIS_API_KEY}`, `X-Org-ID: {ZETARIS_ORG_ID}`, `X-Request-ID: <new uuid4>`
- Body: `{"queryId": "<uuid4>", "sql": "<ONE statement>", "source": "SqlEditor", "limit": N}`
- **Lightning SQL** dialect. **One statement per request**, no trailing `;`, qualified names `<datasource>.<table>` (use `table("communities")`). Reference: http://localhost:8888/redoc/index.html and https://github.com/zetaris/getting-started (its `AGENTS.md`)
- Our Postgres is registered: `scripts/register_zetaris.py` runs `CREATE DATASOURCE resq_pg DESCRIBE BY "…" OPTIONS (jdbcdriver, jdbcurl "jdbc:postgresql://resq-postgres:5432/resq", username, password, fetchsize)` and `REGISTER DATASOURCE TABLES FROM resq_pg`. The description only accepts letters, digits and `_ . - ,` (no spaces). Tables are queried as `resq_pg.<table>`; reserved-word columns (`timestamp`, `datetime`) work unquoted.
- Postgres runs in `docker-compose.yml` as `resq-postgres` on the **`zetaris_default` Docker network** (Zetaris reaches it by container name) and on `127.0.0.1:5433` for the loader. Credentials `RESQ_PG_*` live in `.env`.
- Over Tailscale: Juan's IP is `100.85.62.9`; the UI (`:3000`) listens on all interfaces, the REST API is published with `tailscale serve --tcp 8888` because it only binds to `127.0.0.1`.
- Zetaris **does not read files from the laptop**. Never use port 8889 (internal).

### Talking to Nightshift

- OpenAI-compatible API: `GET /v1/models`, `POST /v1/chat/completions`
- Headers: `Authorization: Bearer {METERLESS_RUNTIME_TOKEN}`, `meterless-app: resq-ai`, `meterless-scope: user`
- `meterless/auto` may route to a non-NVIDIA model: for the demo and the NVIDIA prize, **pin a lane to Nemotron**.
- Known errors: `404 page not found` = URL without `/v1` or a non-chat model; `Function … Not found for account` = model with no endpoint for the account.

### Talking to the World Model service

`GET /health` · `GET /entities` · `GET /facts` (append order) · `GET /audit` · `POST /entities {entities:[{type,id,attrs,at,by}]}` (unchanged rows skipped) · `POST /facts {about_type, about_id, predicate, value, confidence, source:{kind,by,at,runId}}` · `POST /reset`. State persists in `world_service/.world/<namespace>.json` (gitignored). Port `WORLD_PORT` (default 4380).

## 5. Repo structure

```text
RESQ_AI/
├── AGENTS.md · CLAUDE.md (local only) · README.md · requirements.txt · .env.example · pytest.ini
├── smoke_test.py              # checks Zetaris + model (from the official guide)
├── docs/  PLAN.md · TEAM_SETUP.md · protocol.md (rules P1–P8)
├── resq/
│   ├── config.py              # Settings from .env (get_settings)
│   ├── protocol.py            # constants of docs/protocol.md
│   ├── schemas.py             # Assignment, Plan, Route, Event, CriticReview, ResqState
│   ├── llm.py                 # chat / chat_json → Nightshift (or NVIDIA in dev)
│   ├── trace.py               # JSONL trace → logs/trace_<run_id>.jsonl
│   ├── scenario.py            # seed the World Model from SQL; scenario clock
│   ├── world/                 # World Model client (HttpWorld, MemoryWorld)
│   ├── tools/  zetaris.py · routing.py · validators.py · packing.py
│   ├── agents/ intake · reconciler · risk_analyst · planner · critic · explainer · common
│   ├── graph.py               # LangGraph graph
│   └── run.py                 # CLI + execute()
├── world_service/             # Node service over the vendored Meterless World Model reference
├── app/                       # Streamlit UI (to do)
├── docker-compose.yml         # scenario Postgres (resq-postgres) for Zetaris
├── scripts/  generate_data.py · load_postgres.py · register_zetaris.py · run_demo.py
├── data/  README.md · sample/*.csv
├── input_examples/README.md · output_examples/ (reports, plans, traces of a real run)
├── logs/                      # traces (gitignored)
└── tests/                     # 116 tests, all offline
```

## 6. Contracts between modules

Changing a contract = tell the group + record it in §10.

```python
# resq/tools/zetaris.py  (Juan)
def run_sql(sql: str, limit: int = 500) -> list[dict]: ...   # one statement; raises ZetarisError; numbers parsed
def table(name: str) -> str: ...                              # "communities" or "resq_pg.communities"

# resq/llm.py  (Harry)
def chat(messages, lane="fast", tools=None, max_tokens=None) -> dict: ...  # content, reasoning, model, lane, usage, duration_ms
def chat_json(messages, lane="fast", max_tokens=None) -> tuple[object, dict]: ...  # parsed JSON + reply; one repair round

# resq/world/  (Juan)
def get_state() -> dict: ...                 # tables keyed by id + verified facts (status, risk_level, needs, …)
def apply_event(event: dict) -> None: ...    # {"type": "segment_blocked", "id": "T6", "source": "coordinator", "ts": "2020-11-05T10:05:00"}
def history() -> list[dict]: ...             # domain events in write order, each with "seq"
def seed(tables, at) / save_plan(plan, ts) / latest_plan() / reset()
# event types: segment_blocked · segment_reopened · segment_status_verified · shelter_status_verified ·
#              community_status_verified · community_risk_assessed · plan_published
# For a predicate, the most recent observation (ts) wins; ties go to the later write.

# resq/tools/routing.py  (Chema)
def best_route(origin: str, destination: str, state: dict, vehicle_id: str) -> Route | None: ...  # place ids or nodes
def reachability(community_id: str, state: dict) -> str: ...   # "all" | "ford_only" | "none"

# resq/tools/validators.py  (Chema)
def validate_plan(plan: Plan, state: dict) -> list[str]: ...  # empty = valid; each message starts with the rule (P2, P5.1, …)
def critical_minimum_gaps(state: dict) -> list[str]: ...      # why P5.2 cannot be met at all (empty = feasible)

# resq/tools/packing.py
def pack(allocations: list[dict], state: dict) -> PackResult: ...  # assignments + shortfalls

# resq/schemas.py  (everyone; Harry owns)
class Assignment(BaseModel): community_id; origin_id; resource; quantity > 0; vehicle_id; route: list[str]; priority >= 1; reason; evidence: list[str]
class Plan(BaseModel): version; assignments; unserved; risks; confidence 0..1; escalated; changes_vs_previous

# Graph nodes: def node_<agent>(state: ResqState) -> dict   # returns only the fields it updates

# resq/run.py  (Harry) — what the UI calls
def execute(question: str, event: dict | None = None) -> dict: ...
# {"run_id", "request_type", "plan": Plan | None, "report": str (Markdown), "trace": list[dict], "escalated": bool, "reviews"}
```

### Scenario data (tables in Zetaris)

`communities`(id, name, population, pct_children, pct_elderly, vulnerability 1–5, elevation_m, lat, lon, road_node) · `shelters`(id, name, capacity, current_occupancy, road_node) · `warehouses`(id, name, road_node) · `inventory`(warehouse_id, resource, quantity, unit_weight_kg) · `road_nodes`(id, lat, lon) · `road_segments`(id, origin, destination, distance_km, surface, official_status) · `vehicles`(id, type, capacity_kg, can_ford, warehouse_id) · `field_reports`(id, timestamp, source: official|brigade|social_media, object_type, object_id, reported_status, detail) · `rainfall` (Open-Meteo: datetime, precipitation_mm).

Current sample: 14 communities · 4 shelters · 2 warehouses · 16 road nodes · 21 segments · 6 vehicles · 30 reports · 107 hourly rainfall rows. Status vocabularies, scenario story and seeded contradictions: `data/README.md`.

## 7. Conventions for AI agents and people

- **Language:** English for everything in the repo and the demo (rule 9 of §2). Identifiers in `snake_case`/`PascalCase` English.
- **Small changes** focused on the requested task; do not rewrite another member's modules without telling them.
- **Do not invent APIs** for Zetaris or Meterless: check the sources in §4. If unsure, say so and leave a `TODO(verify)`.
- **Models:** only through `resq/llm.py`. No other file creates OpenAI clients. Agents call `llm.chat` / `llm.chat_json` through the module (tests replace them).
- **Data:** only through `resq/tools/zetaris.py` (or `SAMPLE_MODE`). Write portable SQL (it also runs on SQLite) and use `table()`.
- **Protocol numbers** live in `resq/protocol.py`, mirrored in `docs/protocol.md`; agents cite rule ids (`P5.2`).
- **Trace:** every agent step writes one JSONL line (`ts, run_id, agent, input_summary, output_summary, lane, model, duration_ms, iteration`). Never include secrets.
- **Limits:** timeouts on every external call (Zetaris 60 s, model 90 s, World Model 10 s); max. 3 critic rounds; max. 2 retries.
- **Tests:** `pytest` runs offline (SAMPLE_MODE, in-memory World Model, scripted model; see `tests/conftest.py`). Run `pytest` before every commit.
- **Git:** branches `feat/<area>-<topic>`; small commits with English messages; PR to `main`; Juan reviews. Never `git add .env`.
- **When closing a session:** update §8, §9 and §10 of this file.

### How to run

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: py -3.12 -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                   # then fill in real values
python smoke_test.py                                   # 3 PASS expected
pytest                                                 # 116 passed
python scripts/generate_data.py                        # rebuild data/sample/ (add --fetch-rainfall to refresh rainfall)
docker compose up -d && python scripts/load_postgres.py && python scripts/register_zetaris.py   # Zetaris host only

cd world_service && npm install && npm run conformance && npm start   # World Model service on :4380 (own terminal)

python -m resq.run --reset
python -m resq.run --question "How should we distribute aid right now?"
python -m resq.run --event block:T6
python -m resq.run --question "Why did the plan change?"
python scripts/run_demo.py                             # baseline + block T6 + why → output_examples/ (--out <dir> elsewhere)
```

### Environment variables

| Variable | Use |
| --- | --- |
| `ZETARIS_BASE_URL` | Zetaris UI (smoke test) |
| `ZETARIS_REST_URL`, `ZETARIS_ORG_ID`, `ZETARIS_API_KEY` | Zetaris REST API |
| `ZETARIS_DATASOURCE` | Datasource of our tables in Zetaris (default `resq_pg`) |
| `ZETARIS_RAINFALL_TABLE` | Qualified Open-Meteo REST table, if not `<datasource>.rainfall` |
| `RESQ_PG_DB`, `RESQ_PG_USER`, `RESQ_PG_PASSWORD`, `RESQ_PG_PORT` | Scenario Postgres (Zetaris host only); `RESQ_PG_HOST_FOR_ZETARIS` = how Zetaris reaches it (default `resq-postgres:5432`) |
| `METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN`, `METERLESS_MODEL` | Nightshift (primary provider) |
| `MODEL_BASE_URL`, `MODEL_API_KEY`, `NEMOTRON_MODEL` | Active model (Nightshift by default; direct NVIDIA only in development) |
| `LANE_FAST_MODEL`, `LANE_DEEP_MODEL` | Model per lane (both default to `NEMOTRON_MODEL`) |
| `LANE_DEEP_THINKING` | `true` = Nemotron reasoning on the deep lane (default `false`, see §3 model notes) |
| `SAMPLE_MODE` | `true` = run the same SQL on `data/sample/` (SQLite) instead of Zetaris |
| `WORLD_MODEL_URL` | World Model service, e.g. `http://127.0.0.1:4380`; empty = in-memory fallback (dev only) |
| `RESQ_LOGS_DIR` | Where traces go (default `logs/`) |

---

## 8. Current status

**Current phase: 2.** The system runs end to end on **Zetaris data** (`SAMPLE_MODE=false`) + the real World Model service + direct NVIDIA. Not yet on Nightshift. Harry and Chema are working in parallel (branches `feat/llm-nightshift`, `feat/ui-streamlit`); Juan's data work is in `feat/data-zetaris`.

Done:
- [x] Track 3 chosen; RESQ AI idea defined; repo in English (code, docs, contracts)
- [x] Zetaris running on Juan's laptop; `smoke_test.py` 3 PASS (direct NVIDIA)
- [x] Skeleton, `config.py`, `docs/TEAM_SETUP.md`, `docs/protocol.md` (P1–P8)
- [x] Synthetic scenario + Eta rainfall snapshot (`scripts/generate_data.py`, `data/sample/`)
- [x] `run_sql` (Zetaris REST + SAMPLE_MODE on SQLite), `best_route`, `reachability`, `validate_plan`, `critical_minimum_gaps`, `pack`
- [x] `llm.py` with lanes, Meterless headers, retries, JSON repair; thinking off by default
- [x] **R1 closed:** World Model service over the vendored Meterless reference, conformance **8/8**, Python client + in-memory fallback
- [x] Six agents + LangGraph graph + CLI: critic loop (max 3), one model review, escalation with exact gap, re-plan on events, "why" answers
- [x] Real run saved in `output_examples/` (baseline v1 approved after a critic round; block T6 → v2 escalated: critical minimum needs 18,337 kg, fording vehicles carry 13,800 kg)
- [x] `road_nodes` table for the UI map (in the generator, `data/sample/`, `run_sql` and `get_state()`)
- [x] Tailscale up (Juan `100.85.62.9`); Zetaris REST published with `tailscale serve`; Harry and Chema invited
- [x] Scenario in our own Postgres (`docker-compose.yml`, `scripts/load_postgres.py`), registered in Zetaris as `resq_pg` (`scripts/register_zetaris.py`); every agent query returns the same rows as `SAMPLE_MODE`
- [x] Demo on Zetaris data: baseline v1 approved after 2 critic rounds; block T6 → v2 escalated with the same 18,337 kg vs 13,800 kg gap
- [x] `pytest`: **116 passed** (offline, scripted model)

Pending / known issues:
- [ ] Optional: Open-Meteo as a live Zetaris REST table (today rainfall is a snapshot in Postgres)
- [ ] Give Harry (and Chema) a separate Zetaris API token, by private message
- [ ] Nightshift not tested (Harry): lanes, `chat_template_kwargs` forwarding, deep model choice
- [ ] Streamlit UI not started (Chema)
- [ ] Model quality: the Explainer sometimes mixes up facts (e.g. "fording" vs "non-fording"); the Critic's model review sometimes flags non-issues (it can only send a plan back once). Prompt tuning = Harry
- [ ] Reconciler model decisions vary between runs (T11 open vs uncertain), so plans vary slightly; consider temperature 0 for the fast lane
- [ ] `README.md` for judges is a first version; final pass in Phase 4
- [ ] `CLAUDE.md` is gitignored although §5 lists it

## 9. Next steps (in order)

Juan:
1. Merge `feat/data-zetaris` into `main`; send Harry a separate Zetaris API token by private message.
2. Make the Reconciler more stable between runs (temperature 0 or more code-decided objects) and review the Risk Analyst summary.
3. Ask in HackOS whether the vendored World Model reference counts as a working engine (§10, R1).
4. Optional: Open-Meteo as a live Zetaris REST table, if time allows.

Harry (when available): Nightshift + lanes; run `python scripts/run_demo.py` on Nightshift; confirm `chat_template_kwargs`; tune Planner/Critic/Explainer prompts; heavy test (3 scenarios × 5 runs).

Chema (branch `feat/ui-streamlit`): Streamlit UI in `app/streamlit_app.py`, first offline on `output_examples/`, then calling `resq.run.execute()` (plan table, map from `road_nodes` + `road_segments` colored by status, trace panel, escalation banner, "block segment" and "why" buttons); review `routing.py` / `validators.py` and add tests. Juan works in `feat/data-zetaris` on other files; only Juan edits `AGENTS.md` (Chema's notes go in the PR description).

Everyone: 45-minute call to walk through the code and confirm the contracts in §6.

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
| 2026-10-24 | **Everything in the repo and demo is in English**; contracts and tables renamed (`Asignacion`→`Assignment`, `validar_plan`→`validate_plan`, `ejecutar`→`execute`, `comunidades`→`communities`, `tramos`→`road_segments`, …) | International judges; renaming cost nothing because no code existed yet |
| 2026-10-24 | Juan wrote first versions of Harry's and Chema's modules (owners keep ownership) | Both were unavailable and Phase 1 had slipped |
| 2026-10-24 | **R1:** World Model = Node service over the **vendored Meterless reference** (Apache-2.0), same pattern as Meterless' own `agentathon-starter` (which vendors the H-MEM reference). Conformance runs on the vendored code. TODO(verify) with organizers that this counts | Passes conformance without rewriting the engine; our code is the domain mapping and the service |
| 2026-10-24 | Domain state in the World Model: scenario rows = entities (`type:resq:id`), agent conclusions and coordinator actions = facts with provenance; most recent observation wins | Re-plans are explained from the event history; a later-written but older report cannot undo a coordinator block |
| 2026-10-24 | Scenario clock: decision time = latest observation in the data (2020-11-05 10:00); each coordinator event happens 5 scenario minutes after the latest one | Reproducible timestamps; facts stay comparable |
| 2026-10-24 | Thinking off on both lanes by default (`LANE_DEEP_THINKING` to enable) | With thinking, Nemotron used the whole budget or exceeded the 90 s timeout |
| 2026-10-24 | Planner chooses discrete **tiers** (P4.1); code orders by risk (P5.1), gives the P5.2 minimum first and packs vehicles (`packing.py`) | The fast model failed at quantity arithmetic and vehicle packing; decisions stay with the model, math in code |
| 2026-10-24 | New rules: P1 support factor + uncertain only when reports disagree (threshold 0.65); P5.1 order check in code; P8.2 model review can send a plan back once; P8.2.1 infeasible P5.2 escalates instead of looping | Calibrated on the seeded reports and real runs (a lone old "open" report made the main road uncertain; the Critic's model review looped on wording) |
| 2026-10-24 | `SAMPLE_MODE` runs the same SQL on SQLite loaded from `data/sample/` | Identical agent code with and without Zetaris |
| 2026-10-24 | New table `road_nodes(id, lat, lon)`, seeded into the World Model; `get_state()` now includes `road_nodes` | The UI map needs node positions; added on `main` before Chema branches off for the UI |
| 2026-10-25 | Scenario Postgres = `resq-postgres` container on the `zetaris_default` network, host port `127.0.0.1:5433`; tables recreated from `data/sample/` with explicit types; timestamps kept as ISO text | Zetaris (in Docker) reaches it by name; 5432 is taken by Zetaris' own Postgres; text timestamps keep the same string comparisons in Zetaris and SQLite |
| 2026-10-25 | Rainfall lives in Postgres (archive snapshot) instead of a live Open-Meteo REST table | Reproducible runs; the REST table stays optional |
| 2026-10-25 | Zetaris REST published on the tailnet with `tailscale serve --tcp 8888` (UI on `:3000` already listens on all interfaces) | The API container binds to `127.0.0.1` only; no change to the Zetaris bundle |
