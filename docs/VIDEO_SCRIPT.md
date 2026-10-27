# RESQ AI demo video script

Follows the official *Demo Video Guide* of the Open Agent Hackathon 2026. Demo is worth 15 points: judges must quickly see the problem and the user, the agent design, the system running, Zetaris and Meterless doing real work, and the output and why it matters.

- **Target length 3:20** (limit 4:00; a video over 4 minutes does not meet the requirement).
- **Narration is required** (a video with no audio is rejected). English, direct, no long background. Captions are optional but help judges in other languages.
- **File:** `OAH2026-RESQAI-ReasoningArchitecture-Demo.mp4` · MP4 · 1080p · 16:9.
- Every number and trace line on screen must come from a real run. Waits for the model may be cut; inputs and outputs may not be edited.

## Before recording

1. **Services up:** Nightshift (take a fresh token from the Console → Connect → API KEY and put it in `METERLESS_RUNTIME_TOKEN` and `MODEL_API_KEY`; the token changes when Nightshift restarts), Zetaris on Juan's host, World Model service (`cd world_service && npm start`). `.env`: `SAMPLE_MODE=false`, `WORLD_MODEL_URL=http://127.0.0.1:4380`.
2. **Checks:** `python -m resq.llm --check` all PASS with "Meterless Nightshift"; then `python -m resq.run --reset` so the dashboard starts at plan v1.
3. **Screen:** terminal font 18 pt or larger, browser zoom 110–125 %, cursor visible.
4. **Secrets:** close `.env` and the Nightshift API KEY page; clear terminal history (`clear`; PowerShell `Clear-History`); do not show Tailscale IPs or tokens.
5. **Windows ready, in this order:** README on GitHub (top of the page) · architecture slide from the deck · dashboard in **Live** mode · terminal · Zetaris SQL editor · Nightshift **Apps** tab.
6. **Recording:** record the screen in pieces and the voice over the edit (easier than talking while the model runs). Rehearse once; Nemotron does not return identical tiers every run, so rehearse the story, not the exact tiers.

## Shot list

| # | Time | Screen | Narration goal |
| --- | --- | --- | --- |
| 1 | 0:00–0:20 | README header (track line visible) | Track, user, problem |
| 2 | 0:20–0:45 | Dashboard map and plan v1 | Input → output; data is synthetic |
| 3 | 0:45–1:20 | Architecture slide | Agent roles, critique loop, escalation, shared World Model |
| 4 | 1:20–2:20 | Dashboard Live: Plan now → Block segment T6 → Agent trace | Real run and the moment the Critic sends the plan back |
| 5 | 2:20–2:50 | Terminal, Zetaris, Nightshift, World Model timeline | Sponsor technology doing real work |
| 6 | 2:50–3:20 | Escalation banner, "Why did the plan change?", diff | Output, honest limit, impact, closing line |

## 1. Problem (0:00–0:20)

**On screen:** README header: "RESQ AI · Track 3: Reasoning Architecture".

**Voice-over:**

> Our entry is for Track 3, Reasoning Architecture. During a flood, a municipal emergency coordinator has to decide where scarce water, food and vehicles go. But field reports contradict each other, stock doesn't cover every community, and the plan is out of date as soon as a road closes.

## 2. Solution (0:20–0:45)

**On screen:** dashboard: road map, plan version, assignment table.

**Voice-over:**

> RESQ AI takes the scenario data and the coordinator's events, like "road T6 is blocked", and produces a versioned distribution plan: who gets what, on which vehicle and route, why, and what changed since the last version. The municipality and the reports are synthetic; the rainfall is the real Hurricane Eta series from Open-Meteo.

## 3. Agents and collaboration (0:45–1:20)

**On screen:** architecture slide. Point at the Planner ⇄ Critic loop, the escalation branch and the World Model.

**Voice-over:**

> Six agents share one Meterless World Model. The Reconciler decides which conflicting report to believe. The Risk Analyst scores every community. The Planner chooses a delivery tier for each one, and code does the arithmetic: routes, stock and vehicle capacity. It isn't a fixed chain. The Critic checks the plan against the protocol in code, reviews the Planner's reasons with Nemotron, and can send the plan back, up to three rounds. If the protocol can't be met at all, it escalates to the coordinator instead of pretending. The Explainer writes the report and the exact changes.

## 4. Live run (1:20–2:20)

**Action:** in Live mode click **Plan now** (cut the wait) → plan v1 → glance at the **Coordinator brief** tab.

**Voice-over:**

> Here's a real run, on Zetaris data, through Nightshift. The first plan serves the critical river-valley communities first.

**Action:** select `T6` in **Road segment**, click **Block segment** (cut the wait) → plan v2 and the escalation banner → open the **Agent trace** tab.

**Voice-over:**

> Now the coordinator reports that T6, the main paved road into the valley, is blocked. The event goes into the World Model and the whole graph runs again.

**On screen:** the Agent trace with the two Planner and two Critic rows. Zoom on the round-1 Critic row.

**Voice-over** (fill in from the trace of the take you recorded):

> In the trace you can see the agents disagree. In round one the Critic blocked the plan: it flagged [community and reason from the round-1 Critic row]. So the plan went back to the Planner, which revised it, and in round two the Critic approved it. Every step shows the agent, the round, the Nemotron model and the time it took.

Only narrate a rejection that happened in that take. If the live take has none, keep the take and show the Nightshift run in `output_examples/02_block_T6_trace.jsonl` (Critic blocks in round 1 over the C04/C06 priority, approves in round 2), or record another take.

## 5. Sponsor technology (2:20–2:50)

**On screen, quick cuts:**

1. Terminal: `python -m resq.llm --check`: all PASS, "Meterless Nightshift", fast lane `nvidia/nemotron-3.5-lightning-30b-a3b`, deep lane `nvidia/nemotron-3-ultra-550b-a55b`.
2. Zetaris SQL editor: `SELECT id, timestamp, source, reported_status, detail FROM resq_pg.field_reports WHERE object_id = 'T7'` (official "open" vs brigades "flooded"). Alternatively, the header of `python scripts/run_demo.py`: `data=Zetaris · world=meterless-world-model · model=…`.
3. Nightshift **Apps** tab: `Resq Ai` requests on `nvidia/nemotron-…`.
4. Terminal: `python -m resq.world timeline T6`.

**Voice-over:**

> Zetaris is the agents' only data source: every table and field report is read with SQL through its REST API. Here are the contradictory T7 reports the Reconciler weighed. Every model call runs through Meterless Nightshift on NVIDIA Nemotron: a Lightning model for the fast agents and Ultra for the Planner and the Critic. The Meterless World Model keeps every belief with its source and time; this is T6's timeline. And we built the project in Cursor.

## 6. Output and impact (2:50–3:20)

**On screen:** plan v2 with the escalation banner; click **Why did the plan change?**; then the **Risks and changes** tab with the exact diff.

**Voice-over:**

> The result is a plan the coordinator can act on and defend. After the block, the five critical communities can only be reached by fording vehicles. They need 17,952 kilograms of water and food, and those vehicles carry 13,800. RESQ AI delivers a best-effort plan and escalates that exact gap to a human. Asked why the plan changed, it answers from the event history, with the exact changes. Instead of reconciling reports by hand while roads close, the coordinator gets a checked, explained plan in under two minutes. It supports the decision; it doesn't replace the coordinator.

**End card:** `RESQ AI — plans that change when reality does.` · Track 3: Reasoning Architecture · github.com/JuanGualim/RESQ_AI

## After recording

- [ ] Between 1 and 4 minutes; audio clear; screen text readable; plays start to finish
- [ ] Track, user and problem stated; agent roles explained; the Critic's send-back shown in the trace
- [ ] Zetaris, Meterless (Nightshift + World Model) and Nemotron shown doing work; Cursor mentioned
- [ ] Final output and impact shown
- [ ] No keys, tokens, `.env` or Tailscale IPs anywhere in the video
- [ ] Uploaded so that anyone with the link can watch: test it in a private browser window while logged out
- [ ] Backup copy hosted somewhere else, the local MP4 kept, and one teammate has the file
- [ ] Link added to the README (`## Demo video`) and to `docs/SUBMISSION.md`
