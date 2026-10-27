# Team setup

How to get a working RESQ AI environment on each machine. Read `AGENTS.md` first.

| Machine | Who | Mode | Needs |
| --- | --- | --- | --- |
| Linux, Zetaris host | Juan | Full (Zetaris + World Model + direct NVIDIA in development) | Python, Node, Docker, Zetaris bundle |
| Windows, Nightshift host | Harry | Full (Nightshift + Juan's Zetaris over Tailscale) | Python, Node, Nightshift, Tailscale |
| Windows, modest | Chema | `SAMPLE_MODE=true` (no Docker, no Zetaris, no local models) | Python, Node (optional) |

## 1. Install

| Tool | Version | Why |
| --- | --- | --- |
| Python | 3.12 recommended (3.14 works on Linux) | Agents, tools, UI |
| Node.js | 20 or later | World Model service (`world_service/`) |
| Git | any recent | Repo |
| Tailscale | latest | Reach Zetaris (Juan) and Nightshift (Harry) |

## 2. Clone and create the environment

```bash
git clone git@github.com:JuanGualim/RESQ_AI.git
cd RESQ_AI
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

On Windows, if `py -3.12` exists, use `py -3.12 -m venv .venv`.

## 3. Fill in `.env`

Ask for real values **by private message**, never in a group chat or a screenshot.

| Variable | Juan | Harry | Chema |
| --- | --- | --- | --- |
| `ZETARIS_REST_URL` | `http://localhost:8888/api/v1.0` | `http://100.85.62.9:8888/api/v1.0` | not needed (or the same as Harry) |
| `ZETARIS_API_KEY`, `ZETARIS_ORG_ID` | his own token | token from Juan | not needed |
| `MODEL_BASE_URL` | direct NVIDIA (development only) | `http://127.0.0.1:8088/v1` | Harry's Nightshift over Tailscale, or direct NVIDIA |
| `MODEL_API_KEY` | `nvapi-…` | Nightshift runtime token | Nightshift token or `nvapi-…` |
| `SAMPLE_MODE` | `false` | `false` | `true` |
| `WORLD_MODEL_URL` | `http://127.0.0.1:4380` | `http://127.0.0.1:4380` | empty (in-process fallback) or `http://127.0.0.1:4380` |

## 4. Check

```bash
python smoke_test.py     # Juan and Harry: 3 PASS. Chema: only the model check matters
pytest                   # all tests pass on every machine
```

## 4b. Zetaris host only (Juan): scenario Postgres and Tailscale

```bash
docker compose up -d                       # resq-postgres on the zetaris_default network (RESQ_PG_* in .env)
python scripts/load_postgres.py            # create the 9 tables and load data/sample/ (prints row counts)
python scripts/register_zetaris.py         # CREATE DATASOURCE resq_pg + REGISTER DATASOURCE TABLES, then verifies
python scripts/register_zetaris.py --verify   # later: check every table through Zetaris
```

After regenerating the data, run `load_postgres.py` again; the datasource does not need to be registered again.

The Zetaris REST API only listens on `127.0.0.1`, so it is published to the tailnet with Tailscale:

```bash
sudo tailscale serve --bg --tcp 8888 tcp://127.0.0.1:8888
tailscale ip -4                            # Juan: 100.85.62.9
```

Harry and Chema then use `ZETARIS_BASE_URL=http://100.85.62.9:3000` and `ZETARIS_REST_URL=http://100.85.62.9:8888/api/v1.0`.

## 5. World Model service

```bash
cd world_service
npm install
npm run conformance      # World Model conformance suite: all checks must pass
npm start                # listens on http://127.0.0.1:4380
```

## 6. Run the agent

```bash
python -m resq.run --question "How should we distribute aid right now?"
python -m resq.run --event block:T6
```

## 7. Check the Meterless provider

```bash
python -m resq.llm --check   # connection, authorization, model discovery, one request per lane
```

On the demo machine the first line must say `Meterless Nightshift`; a `401` means the Runtime token must be copied again from the Nightshift Console.

Windows from scratch: the problems Harry hit, step by step, are in [`windows_install_notes.md`](windows_install_notes.md) (Tailscale with a GitHub login creates its own tailnet; join through the invitation instead).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `404 page not found` from the model | `MODEL_BASE_URL` is missing `/v1`, or the model is not a chat model |
| Zetaris `401` | Bad `ZETARIS_API_KEY` |
| Zetaris `400` | Bad `ZETARIS_ORG_ID` |
| Zetaris unreachable from Windows | Tailscale is off on one side, or Juan's Zetaris is stopped |
| `World Model service unreachable` | Start it with `npm start` in `world_service/`, or leave `WORLD_MODEL_URL` empty to use the in-process fallback |
