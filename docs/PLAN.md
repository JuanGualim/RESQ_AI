# RESQ AI — Team phased plan

**Open Agent Hackathon 2026 · Track 3: Reasoning Architecture**
Version 2 · Friday, October 23, 2026 (split adjusted to the team's machines) · times in **Guatemala time (UTC-6)**
Submission: **Tuesday, October 27, 17:45** (hard deadline). Internal target: **Tuesday 27, 12:00**.

> The project's living document is `AGENTS.md` in the repo. This plan is the reference for phases and the work split; if something changes, record it first in `AGENTS.md` ("Decision log" section).

---

## 1. What we are building

**In one sentence:** RESQ AI helps a municipal emergency coordinator decide how to distribute aid during a flood. It combines data on communities, shelters, roads, rainfall and contradictory field reports, prioritizes using protocol rules, and delivers a distribution plan that re-plans itself when reality changes, explaining why it changed.

| Piece | Definition |
| --- | --- |
| User | A municipality's emergency coordinator (municipal emergency operations center) |
| Decision | Which communities to serve first, with which resources, from which warehouse or shelter, with which vehicle and along which route |
| Output | Versioned plan (v1, v2, …): assignments with priority, route, reason and evidence; on a re-plan, what changed and why |
| WOW moment | A road gets blocked live (a button in the UI). The agents reconcile reports, re-plan, the critic validates and the report explains the change |

### Why Track 3

| What the track asks for | How RESQ AI delivers it |
| --- | --- |
| Data | Communities, shelters, warehouses, roads, vehicles, reports and rainfall, queried in Zetaris |
| Knowledge | Protocol priority rules (vulnerability, children and elderly, capacity) |
| Memory / state | World Model (Meterless): shared state and events; previous plan to compare against |
| Reasoning | Reconciler, risk analyst, planner and critic that check each other |
| Reliable decisions and actions | Plan validated by hard rules in code; re-plan on events; escalation to a human |

### Scope

**In:** 1 fictional municipality · 12–15 communities · 3–4 shelters · 2 warehouses · ~20 road segments as a graph · 5–8 vehicles · ~30 field reports (some contradictory) · real Open-Meteo rainfall for reference coordinates · 3 test scenarios.

**Out:** real GPS routes, real personal data, hydrological models, mobile app, login or multi-user.

---

## 2. Architecture

```text
Coordinator (Streamlit UI)
   │  question  /  event: "block segment T7"
   ▼
[Intake] ── classifies the request: situation · plan · event · "why?"
   ▼
[Reconciler] ── official reports vs. brigades vs. social media ──► facts + confidence ──► World Model
   ▼
[Risk Analyst] ── SQL in Zetaris ──► risk index per community ──► World Model
   ▼
[Planner] ── rules + routing tool + capacities ──► plan vN
   ▼
[Critic] ── validates hard rules (code) and reasons (LLM)
   │   ✗ ──► back to the Planner with feedback (max. 3 rounds)
   │   ✗✗ no solution or low confidence ──► ESCALATE: "requires a human decision"
   ✓
[Explainer] ── final plan + differences vs. the previous version and their cause (World Model events)

Shared services: Zetaris (data) · World Model (state + events) · Nightshift → Nemotron (models) · JSONL trace
```

**Design principle: the LLM decides and explains; the code computes.** Shortest routes, capacities, inventory and hard validations are deterministic functions. Agents reason over their results. This keeps the system reproducible and stops it from inventing routes or numbers.

### Agents

| Agent | What it does | Model (lane) | Tools | Writes to |
| --- | --- | --- | --- | --- |
| Intake | Classifies the request and picks the flow | Fast | Rules or Scout Intent (optional) | Trace |
| Reconciler | Decides the real status of road segments and shelters when reports contradict each other, with confidence and justification | Fast | `run_sql` | World Model |
| Risk Analyst | Computes risk per community: rainfall, elevation, vulnerability, accessibility | Fast | `run_sql` | World Model |
| Planner | Assigns resources, vehicles and routes according to priority rules | Deep | `best_route`, inventory, capacities | Plan |
| Critic | Checks hard rules (capacity, blocked segments, critical communities left unserved, suitable vehicle) and that every reason has evidence | Deep | Code validators | Feedback / escalation |
| Explainer | Writes the final plan and the "what changed and why" | Fast | World Model (event history) | Report |

Nightshift lanes (running on Harry's machine): **fast** = `nvidia/nemotron-3.5-lightning-30b-a3b` (verified) · **deep** = a Nemotron super (to confirm which one responds with our account).

### Sponsor technology

| Sponsor | Role in RESQ AI | Mandatory |
| --- | --- | --- |
| Zetaris | Only data source: scenario Postgres registered in Zetaris + Open-Meteo API as a REST table, all via SQL | Yes |
| Meterless World Model | Shared state of communities, road segments and shelters; every change is an event; the history explains the re-plans | Yes (engine) |
| Meterless Nightshift | The app's primary AI provider (OpenAI-compatible API) | Yes |
| Cursor | Development environment for all 3 | Yes |
| NVIDIA Nemotron | Lane models, served by Nightshift. Eligible for the DGX Spark prize | Recommended |
| H-MEM / Scout Intent | Lessons from previous emergencies / request classification | Optional, only if time allows |

### Scenario data

Lives in **our own Postgres** (Docker container on Juan's machine) registered as a data source in Zetaris, because Zetaris does not read CSVs from the laptop. Generated with `scripts/generate_data.py` (fixed seed), with a copy saved in `data/sample/` for the no-services mode (`SAMPLE_MODE`).

| Table | Main columns |
| --- | --- |
| `communities` | id, name, population, pct_children, pct_elderly, vulnerability (1–5), elevation_m, lat, lon, road_node |
| `shelters` | id, name, capacity, current_occupancy, road_node |
| `warehouses` / `inventory` | id, name, road_node / warehouse_id, resource, quantity, unit_weight_kg |
| `road_segments` | id, origin, destination, distance_km, surface, official_status |
| `vehicles` | id, type, capacity_kg, can_ford, warehouse_id |
| `field_reports` | id, timestamp, source (official · brigade · social_media), object_type, object_id, reported_status, detail |
| `rainfall` (REST, Open-Meteo) | datetime, precipitation_mm |
| `docs/protocol.md` | Priority rules (domain knowledge) |

Contradictions are **seeded on purpose** (e.g. the official report says "T7 open", two brigades say "T7 flooded"). The agent must discover them; results are never written in the code.

---

## 3. Team and responsibilities

The split follows each person's machine:

- **Juan** uses Linux, so he cannot run Nightshift. He develops with direct NVIDIA.
- **Harry** has Windows and the best machine. He hosts Nightshift and handles heavy testing and the demo.
- **Chema** gets deterministic, small, well-defined pieces that are tested with `pytest` and `SAMPLE_MODE`, with no Docker, no local Zetaris and no local Nightshift.

| Member | Machine | Role | Owns |
| --- | --- | --- | --- |
| **Juan** | EndeavourOS (Linux) · **Zetaris** host | Data, state and integration (tech lead) | Zetaris up during sessions · scenario Postgres · `scripts/generate_data.py` · `data/sample/` · Open-Meteo table · `run_sql` · `SAMPLE_MODE` · **World Model** (service + Python client + conformance) · **Reconciler** and **Risk Analyst** agents · `config.py` · PR reviews · `AGENTS.md` · final README · **uploads the submission to HackOS** |
| **Harry** | Windows, powerful machine · **Nightshift** host | Agents, models and heavy testing | Nightshift, its lanes and its Tailscale exposure · `resq/llm.py` · `schemas.py` · LangGraph graph · `run.py` · **Planner**, **Critic** and **Explainer** agents · critic loop and escalation · JSONL trace · **end-to-end test battery with Nightshift** · from-scratch install on Windows · Nemotron evidence · `output_examples/` · demo machine · **video recording** |
| **Chema** | Windows | Deterministic tools, UI and communication | `docs/protocol.md` · `resq/tools/routing.py` (`best_route`) + tests · `resq/tools/validators.py` + tests · **Intake** agent (rule-based) · Streamlit UI on sample data · `input_examples/` · `SAMPLE_MODE` install test on his machine · video script · slide deck · draft of the usage README |

Everyone: test scenarios, review the demo script and update `AGENTS.md` at the end of each session.

**Why this split:**

- Chema works almost entirely locally with pure functions and data from `data/sample/`, so his machine never loads Docker, Zetaris or models. His pieces are critical (routing and validators), but they have a closed spec and tests, and Juan reviews them.
- Harry concentrates what needs Nightshift close by: prompts, the critic loop, repeated tests, latency measurement and the live demo, which must use Nightshift.
- Juan concentrates what lives next to Zetaris (data and SQL-based agents) and the World Model. The World Model runs on Node, which works fine on Linux, and does not need Nightshift.

### Host availability

| Service | Host | When it must be up | Access for the others |
| --- | --- | --- | --- |
| Zetaris (UI `:3000`, REST `:8888`) | Juan | Work blocks agreed in chat + all of Phases 3–4 | Tailscale (Juan's IP) |
| Nightshift (`:8088/v1`) | Harry | Work blocks + tests + demo; laptop plugged in and without sleep | Tailscale. TODO(verify): if Nightshift only listens on `127.0.0.1`, expose it with `tailscale serve` or `netsh interface portproxy` |
| World Model (Node service) | Whoever runs the agent (each one locally) | Whenever the graph runs | `WORLD_MODEL_URL=http://127.0.0.1:<port>` |

If Nightshift is unavailable, everyone develops with direct NVIDIA, which is only allowed in development and is configured in `.env`.

---

## 4. Phases

**Parallel work rule:** nobody waits for anybody. Each owner first publishes **a stub** with the §5 contract (sample data, in-memory World Model, fake `chat()`) and then replaces it with the real version without changing the signature.

### Phase 0 — Kickoff · Friday 23, until 14:00

Goal: all three with a working environment, contracts agreed and R1 decided.

- [ ] **Juan:** invite collaborators on GitHub · create `docs/TEAM_SETUP.md`, which is referenced today but **does not exist** · Tailscale + expose Zetaris · folder skeleton from §5 of `AGENTS.md` + `resq/config.py`
- [ ] **Juan:** run the World Model *IMPLEMENT → Run the 90-second proof* on Linux and close the R1 decision (see §7)
- [ ] **Harry:** install Nightshift + NVIDIA provider · confirm which Nemotron *super* responds for the deep lane · expose it over Tailscale · share URL and token **privately** · disable sleep
- [ ] **Chema:** Python 3.12 + venv + `requirements.txt` · `smoke_test.py` (Juan's Zetaris over Tailscale + model) · read `AGENTS.md` · start `docs/protocol.md`
- [ ] **45-minute call (~12:00):** confirm the data schema and the §5 contracts and record them in `AGENTS.md`

**Gate:** smoke test with 3 PASS on all 3 machines (Juan with direct NVIDIA; Harry and Chema with Nightshift), contracts written and R1 decided.

### Phase 1 — End-to-end MVP · Friday 23, 14:00 → Saturday 24, 12:00

Goal: a question goes in, a v1 plan (ugly but real) comes out, with data from Zetaris and Nemotron via Nightshift.

| Who | Task | Milestone |
| --- | --- | --- |
| Juan | `generate_data.py` (fixed seed) → **`data/sample/` published first**, because it unblocks everyone | **Fri 18:00** |
| Juan | In-memory `resq/world/` stub with the real contract | Fri 20:00 |
| Juan | Postgres + registration in Zetaris + `run_sql` + 10 key queries tested | Sat 10:00 |
| Juan | Real World Model (Node service) + Python client + **conformance green** | Sat 12:00 (may slip to Sat afternoon) |
| Harry | `schemas.py` (shared contract) | **Fri 18:00** |
| Harry | `llm.py`: `fast`/`deep` lanes, Meterless headers, 90 s timeout, max. 2 retries | Fri 22:00 |
| Harry | Minimal `graph.py` Risk Analyst → Planner → Explainer + `run.py` + JSONL trace | Sat 12:00 |
| Chema | `docs/protocol.md` closed (numbered priority rules, so they can be cited as evidence) | Fri 20:00 |
| Chema | `best_route` (networkx over `road_segments`; skips blocked segments and flooded segments for vehicles that cannot ford) + `tests/test_routing.py` | Sat 12:00 |

**Gate (Sat 24, 12:00):** `python -m resq.run --question "..."` prints a v1 plan with valid routes, using either Zetaris data or `SAMPLE_MODE`.

### Phase 2 — Real multi-agent system · Saturday 24, 12:00 → Sunday 25, 22:00

Goal: the behavior the judges reward.

- [ ] **Chema:** `validators.py` + tests: vehicle capacity, sufficient inventory, route without blocked segments, vehicle suitable for the segment, critical communities left unserved, IDs that exist. **First 4 rules before Sat 18:00**, because the Critic depends on them
- [ ] **Chema:** rule-based Intake agent + tests · Streamlit UI v1 on `output_examples/` (schematic map of nodes and segments, plan table, trace panel)
- [ ] **Harry:** Critic (Chema's validators + LLM review of reasons and evidence) · loop of max. 3 rounds · escalation branch · event-triggered re-plan · `changes_vs_previous` from `world.history()`
- [ ] **Harry:** publish 2–3 real plans in `output_examples/` for Chema's UI (Sat 20:00)
- [ ] **Juan:** Reconciler and Risk Analyst with real SQL · seeded contradictory reports · Open-Meteo table · 3 test scenarios · full `SAMPLE_MODE` · World Model as the shared state of all agents
- [ ] **Check-in Sat 24, 20:00 (20 min):** "if we submitted tomorrow, what would fail?"
- [ ] **Harry, Sun 25 afternoon, first heavy test:** 3 scenarios × 5 runs with Nightshift. Log latency per agent, critic rounds, failures and escalations in `logs/`, and share a summary

**Gate (Sun 25, 22:00):** blocking 2 different segments produces 2 different and correct re-plans, with the critic loop trace, and the heavy test shows no unexplained failures.

### Phase 3 — Product and reliability · Monday 26, until 14:00

- [ ] **Harry + Chema (pairing, on Harry's machine):** connect the UI to the real graph ("block segment" button, "why did it change?" panel)
- [ ] **Harry:** timeouts, bounded retries and honest errors · fixed Nemotron lane and screenshots of the Nightshift logs · **second heavy test** (3 scenarios × 10 runs + both events) · from-scratch install on Windows in full mode · generate the final `output_examples/`
- [ ] **Chema:** polish the UI · **from-scratch install in `SAMPLE_MODE` on his machine**, proving a judge on Windows can run it · README draft (install and usage) · `input_examples/`
- [ ] **Juan:** `data/README.md` · check that the 9 rules of §2 of `AGENTS.md` are met · search the whole git history for secrets (`git log -p | grep -E "nvapi-|Bearer "`) · fix bugs and merge PRs
- [ ] Only if time allows: H-MEM or Scout Intent

**Monday 26, 14:00: FEATURE FREEZE.** From here on, only bug fixes.

### Phase 4 — Package and submit · Monday 26, 14:00 → Tuesday 27, 12:00

- [ ] **Mon 16:00, full demo rehearsal** on Harry's machine (local Nightshift + Juan's Zetaris over Tailscale), following the §8 script. All 3 connected
- [ ] **Harry:** record the video Monday night (plus a **backup recording** of the full flow in case the network fails) · screenshots for the deck · edit the video
- [ ] **Chema:** slide deck (browser-based tool, nothing heavy) · final video script · check that the README is understandable without context
- [ ] **Juan:** final README, sponsor explanation, declaration of prior components, `.env.example`, last pass over the §9 checklist
- [ ] **Tuesday 27, 12:00: Juan uploads everything to HackOS.** 12:00 to 17:45 is only an emergency buffer

---

## 5. Contracts between parts

So we can work in parallel without stepping on each other. Changing a contract = tell the group and record it in `AGENTS.md`.

```python
# resq/tools/zetaris.py  (Juan)
def run_sql(sql: str, limit: int = 500) -> list[dict]: ...   # one statement; raises ZetarisError

# resq/llm.py  (Harry)
def chat(messages: list[dict], lane: str = "fast", tools: list | None = None) -> dict: ...  # lane: "fast" | "deep"

# resq/world/  (Juan)
def get_state() -> dict: ...                 # communities, road segments, shelters with their current status
def apply_event(event: dict) -> None: ...    # {"type": "segment_blocked", "id": "T7", "source": ..., "ts": ...}
def history() -> list[dict]: ...             # events in order

# resq/tools/routing.py  (Chema)
def best_route(origin: str, destination: str, state: dict, vehicle_id: str) -> Route | None: ...

# resq/tools/validators.py  (Chema)
def validate_plan(plan: Plan, state: dict) -> list[str]: ...  # empty list = no violations; each message cites IDs

# resq/schemas.py  (everyone; Harry creates it)
class Assignment(BaseModel): community_id; origin_id; resource; quantity; vehicle_id; route: list[str]; priority: int; reason: str; evidence: list[str]
class Plan(BaseModel): version: int; assignments: list[Assignment]; unserved: list[str]; risks: list[str]; confidence: float; escalated: bool; changes_vs_previous: list[str]

# Graph nodes (each owner implements theirs)  (Harry defines, everyone uses)
def node_<agent>(state: ResqState) -> dict: ...   # returns only the fields it updates

# resq/run.py  (Harry) — what Chema's UI calls
def execute(question: str, event: dict | None = None) -> dict: ...  # {"plan": Plan, "trace": list[dict], "escalated": bool}
```

---

## 6. Way of working

- **Language:** everything that lands in the repo or the demo is in English (code, identifiers, docs, prompts, UI, commits). Team chat can stay in Spanish.
- **Branches:** `feat/<area>-<topic>` → Pull Request to `main`; Juan reviews; merge at least once a day.
- **Short daily check-ins (15 min):** 10:00 and 21:00. Everyone says what they finished, what is next and what blocks them.
- **At the end of each session:** update sections 8–10 of `AGENTS.md` (status, next steps and decisions).
- **Blockers:** if someone is stuck for more than 45 min, tell the group; if it continues, ask in HackOS (#help desk, sponsor channel or mentors).
- **Secrets:** never in the repo, public chats or screenshots. Tokens only by private message.
- **AI agents** (Cursor, Claude Code, Codex): read `AGENTS.md` first; small changes; run tests before every commit.
- **Host machines:** Zetaris (Juan) and Nightshift (Harry) up during the agreed work blocks.
- **Chema's machine:** works with `SAMPLE_MODE=true` and `pytest`. Heavy or long tests are requested from Harry.

---

## 7. Risks and plan B

| # | Risk | Plan B |
| --- | --- | --- |
| R1 | The Meterless engines are in TypeScript and the agent is in Python. Conformance runs with `WORLD_MODEL_IMPL=<index.ts> npx tsx conformance/runner.ts`, so it needs a TS implementation | **Recommended: (b)** the World Model as a small Node service (TS implementation that passes conformance + HTTP with `get_state`/`apply_event`/`history`), called from Python by `resq/world/`. The alternative (a), implementing it in Python, requires writing a TS adapter for conformance and is more work. TODO(verify): whether wrapping the `reference/` implementation is enough or the judges expect our own, generated with the *IMPLEMENT* prompt |
| R2 | Nightshift only runs on Harry's machine, and Juan (Linux) cannot install it | Direct NVIDIA for development; the demo, the heavy test and the video are done on Harry's machine with Nightshift; laptop plugged in and without sleep |
| R3 | Zetaris or Nightshift not reachable over Tailscale | Check ports and `tailscale serve`; meanwhile, `SAMPLE_MODE` or direct NVIDIA |
| R4 | Zetaris does not read local CSVs | Our own Postgres registered as a data source |
| R5 | The judges cannot bring up Zetaris + Nightshift | Clear README, `SAMPLE_MODE`, video, `output_examples/` and traces |
| R6 | The model invents data | Hard validations in code, critic, every assignment references real IDs |
| R7 | Scope creep | Gates per phase; freeze on Monday 14:00 |
| R8 | RAM on Juan's machine (Zetaris + Postgres + World Model) | Close apps, zram on, `docker compose stop` when unused; the World Model is a light Node process |
| R9 | Chema's machine is limited | No Docker or local models; `SAMPLE_MODE` + `pytest`; integration by pairing on Harry's machine |
| R10 | The demo depends on 2 machines (Juan's Zetaris + Harry's Nightshift) and on the network | Rehearsal on Mon 16:00; backup recording; `SAMPLE_MODE` with Nightshift as live plan C |
| R11 | Phase 1 has 3 fronts that depend on each other | Stubs with the real contract from Friday (`data/sample/`, in-memory World Model, `schemas.py` at 18:00) |

---

## 8. Video script (max. 4 min)

Harry records it on his machine with real Nightshift. Chema writes the final script.

1. **0:00–0:30** — The problem: in a flood, reports contradict each other and plans go stale within minutes. User: municipal coordinator.
2. **0:30–1:30** — First plan: risk per community, assignments, routes and the critic trace rejecting and correcting something.
3. **1:30–2:30** — WOW: a segment gets blocked live → reconciliation → re-plan → "what changed and why".
4. **2:30–3:15** — Architecture and sponsors: Zetaris (SQL), World Model (events), Nightshift → Nemotron (lane logs), Cursor.
5. **3:15–3:45** — Outcome for the user, limitations and next steps.

---

## 9. Submission checklist

- [ ] 1–4 min video uploaded
- [ ] Slide deck: problem and users, solution, agent architecture, stack, use of Zetaris and Meterless and what was unique about it, screenshots, future improvements
- [ ] Public repo with README (install, usage, dependencies), `.env.example`, `data/README.md`, examples and traces
- [ ] Sponsor explanation: Zetaris, Meterless (engine + Nightshift), Cursor, NVIDIA
- [ ] Prior components declared (the smoke test comes from the official guide)
- [ ] Zero secrets in the repo: no file or commit with real keys (`nvapi-…`, Zetaris or Nightshift tokens)
- [ ] From-scratch install test done: Windows in full mode (Harry) and `SAMPLE_MODE` on a limited machine (Chema)
- [ ] Everything in English (code, docs, UI, prompts, commits)
- [ ] Uploaded before Tuesday 27 at 12:00
