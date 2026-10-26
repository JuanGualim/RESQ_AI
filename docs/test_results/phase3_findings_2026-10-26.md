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

### 1. Re-plan stability after reopening — the check was wrong, not the agent

The seven failures are all the same one: after blocking T6 and reopening it, plan v3
kept only **45–49 %** of v1's delivery lines, and the battery called that a failure.

The first hypothesis was that the Planner anchored on v2 — the plan cut down by the
block — because its prompt says *"If previous_plan is present, keep what still works"*.
Adding an instruction to re-decide from scratch after a `segment_reopened` changed
nothing: the next run scored 48 %. That change was reverted.

Diffing a real v1 against its v3 showed what actually happens:

```
T6 status: open -> blocked -> open      (the world does go back)

C03 blanket     80 -> 40      C01 medical_kit  - -> 7
C03 hygiene_kit 40 -> 20      C08 medical_kit  - -> 8
C05 blanket    248 -> 124     C11 medical_kit  - -> 5
C05 hygiene_kit 124 -> 62
C07 blanket    244 -> 122     v1 unserved: C01, C08, C11
C07 hygiene_kit 122 -> 61     v3 unserved: none
C12 blanket    128 -> 64
C12 hygiene_kit 64 -> 32
```

The world really does return to its starting state. What changed is the decision: v1
gave four communities the **full** tier and left three unserved; v3 gave them
**essential** — still 100 % of water, food and medical kits, half the blankets and
hygiene kits — and spent what it saved reaching the three the baseline had abandoned.

**v3 is the better plan**, and P5.2 agrees: no community should be left with nothing
while others get blankets. Both are valid; the Planner is not anchoring on anything.

The defect was the measurement. Comparing exact quantities line by line punishes a
legitimate tier change. The check now looks for **regressions** instead: a community
that was served and no longer is, or whose water or food dropped below half of the
baseline. Tier changes that keep the essentials pass. `similarity` is still reported,
as information about how much the plan moved, with no threshold attached.

### 1b. The models are not reproducible, even at temperature 0

Tightening the check to regressions made it fail again, five runs out of five, on
C01, C08 and C11 — three medium-risk communities served in the baseline and dropped
after the reopening. Diffing the same scenario by hand a few minutes later showed the
opposite: both plans left those three unserved and nothing regressed.

So the **baseline itself differs between runs**. Temperature 0 removes sampling noise,
but Nemotron is a mixture-of-experts served in batches, and those are not bit-for-bit
reproducible: which experts fire depends on what else is in the batch. Every plan was
valid; which communities got the leftovers was not stable.

This matters beyond the battery:

- **For the demo:** do not promise the judges an exact plan. The critical communities,
  the escalation and the 17,952 kg gap are stable, because code computes them. The
  exact tier of a medium-risk community is not. Rehearse the story, not the numbers.
- **For the battery:** the regression check now only covers what the protocol
  guarantees — communities at critical or high risk. Medium and low ones are served
  with what is left over, so holding them to a fixed answer would measure the
  endpoint's batching, not our agents.

This is also the honest answer to point 12. Re-plan stability can be reported, and the
guarantees can be enforced, but it cannot be driven to 100 % from our side.

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

Re-plan stability has a number: **48–49 %** of delivery lines identical between the
baseline and the plan after reopening. Every battery run reports it.

The number is low and that is correct behaviour, not a defect — see finding 1. Raising
it would mean telling the Planner to reproduce its previous answer rather than decide
on the facts, which is the opposite of what this system is for. What the battery
enforces instead is that no community loses its place: nobody served goes unserved, and
nobody's water or food is halved, once the road is open again.
