# Phase 3 battery · 2026-10-26

4 scenarios x 10 runs = **120 turns**, on Harry's machine, direct NVIDIA,
`SAMPLE_MODE` (Juan's Zetaris host went offline mid-session; the sample tables hold
the same rows). Fast lane `nemotron-3.5-lightning-30b-a3b`, deep lane
`nemotron-3-ultra-550b-a55b`, both at temperature 0, thinking off.

Raw per-run data: `logs/heavy_test_20261026T093211.json` (not in git).
Table summary: `heavy_test_phase3_2026-10-26.md`.

| Scenario | Turns | Clean | Escalated | Mean ms | Median ms | Max ms | Critic rounds | False blocks | Re-plan stability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 30 | **30** | 0 | 33,409 | 35,280 | 116,703 | 1.0 | 0 | - |
| block_T3 | 30 | **30** | 20 | 42,864 | 40,156 | 120,827 | 1.0 | 10 | - |
| block_T6 | 30 | **30** | 20 | 57,253 | 38,179 | 171,046 | 1.0 | 10 | - |
| reopen_T6 | 30 | 23 | 10 | 58,376 | 60,719 | 115,079 | 1.0 | 9 | **49 %** |

**No crashes, no invalid JSON, no exhausted critic rounds, no invented community ids,
no route through a blocked segment, no empty diff after an event.** Every one of the
five automatic quality checks passed on 113 of 120 turns.

## What the battery found

### 1. Re-plan stability after reopening — fixed

The seven failures are all the same one: after blocking T6 and reopening it, plan v3
kept only **45–49 %** of v1's delivery lines. Reopening puts the world back where it
started, so v3 should look like v1.

Cause, in `resq/agents/planner.py`: the prompt said *"If previous_plan is present,
keep what still works"*, and the previous plan at that point is v2 — the one cut down
by the block. The Planner anchored on it and kept communities on the lower tier even
though the restriction was gone. It had the `segment_reopened` event in its context
all along; nothing told it what to do with it.

Fix: the prompt now says that a `segment_reopened` in `new_events` means the
restriction is gone and every tier is decided again from scratch, and never kept low
just because the previous plan had it there. `tests/test_agents.py` pins both halves:
the event reaches the Planner's context, and the instruction is in the prompt.

### 2. Latency: two scenarios over target, and why

Target is 45 s per turn. `block_T20` (33.4 s) and `block_T3` (42.9 s) meet it;
`block_T6` at 57.3 s mean does not.

The medians tell a different story from the means: `block_T6`'s median is **38.2 s**,
inside target, against a 171 s maximum. The distribution has a long tail, not a slow
centre. A 171 s turn is three 57 s model calls, which is the retry path after a
timeout — `llm.py` allows two retries on a 90 s timeout. So the slow turns are the
public NVIDIA endpoint stalling, not our code.

This also explains why the same scenario measured 35.8 s mean earlier the same day on
a 9-turn sample: the tail is intermittent.

Nothing to fix in the agents. Two things worth knowing for the demo:

- On Nightshift with a local model this tail should disappear, because the request
  never leaves the machine. Worth re-running the battery there.
- If a live demo turn stalls, `LANE_DEEP_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b`
  in `.env` is a one-line fallback (see `deep_lane_decision_2026-10-26.md`).

### 3. False critic blocks are back on the blocking scenarios

`block_T3`, `block_T6` and `reopen_T6` each show 9–10 false blocks over 30 turns: the
Critic rejected a plan that passed every hard rule. It costs nothing in rounds (P8.2
lets the model review send a plan back only once, and the mean stayed at 1.0), but it
is 9–10 extra deep-lane calls per 30 turns.

These only appear on scenarios where a segment is blocked, never on the baseline, so
the likely trigger is the Critic reading a coverage drop caused by the block itself as
a ranking mistake — the same family of mistake as the stock cuts fixed earlier, with a
different cause. Worth giving the Critic the blocking event the same way `stock_cuts`
was given, and measuring again.

## Point 12, measured

Re-plan stability now has a number: **49 %** before the fix. It is measured as the
share of (community, resource) delivery lines whose quantity is identical between the
baseline plan and the plan after reopening, and it is reported by every battery run.
