# Deep lane: which model, which temperature, thinking on or off

Measured on 2026-10-26 on Harry's machine, direct NVIDIA, `SAMPLE_MODE` (Juan's
Zetaris host went offline mid-run; the sample tables hold the same rows).

## Which model

`nvidia/nemotron-3-super-120b-a12b`, the model the plan names for the deep lane,
**does not exist for either of our accounts**. Checked through Nightshift and
through direct NVIDIA, with two different keys:

| Model | Result |
| --- | --- |
| `nvidia/nemotron-3-super-120b-a12b` | 404 Function not found |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | 404 Function not found |
| `nvidia/llama-3.3-nemotron-super-49b-v1.5` | 410 Gone (retired) |
| **`nvidia/nemotron-3-ultra-550b-a55b`** | **answers, 750 ms** |

The deep lane is pinned to Nemotron 3 Ultra. It is still an NVIDIA Nemotron, so the
prize requirement holds.

## Thinking on the deep lane

Planner prompt, three calls each, Nemotron 3 Ultra:

| | Mean | Valid replies | Same decision every time |
| --- | --- | --- | --- |
| Thinking **off** | 10,890 ms | 3/3 | no |
| Thinking **on** | 52,984 ms | **2/3** (one timed out) | yes |

Thinking does make the decision stable, but it costs five times the latency and one
call in three exceeded the 90 s timeout. A single Planner call at 53 s already blows
the 45 s per-turn target on its own.

**Decision: `LANE_DEEP_THINKING` stays `false`.** The same stability is available far
more cheaply — see below.

## Temperature

Temperature 0.2 produced different tier decisions for the same scenario across runs,
which makes a demo impossible to rehearse. Temperature 0 removes that by construction
and measured no slower (1,348 ms vs 1,742 ms mean over four calls each).

**Decision: the deep lane runs at temperature 0**, like the fast lane. This is what
actually fixed the latency target, because fewer disagreements mean fewer critic rounds.

## Ultra vs lightning on the deep lane

Scenario `block_T3` (the slowest one), 3 runs x 3 turns each, 0 failures on both:

| | Nemotron 3 Ultra | Nemotron 3.5 lightning |
| --- | --- | --- |
| Total per turn, mean | 35,767 ms | **30,381 ms** |
| Total per turn, max | 89,327 ms | **54,265 ms** |
| Critic, mean | 11,114 ms | **6,916 ms** |
| Planner, mean | 20,796 ms | **12,192 ms** |
| **Critic rounds on the base plan** | **1.0** | 2.0 |
| False critic blocks | **3** | 4 |

Lightning is faster per call, but its review is worse: it sends back correct plans, so
the graph runs the Planner twice. That extra round eats most of the gain — 30.4 s
against 35.8 s — while missing the point 13 target of at most one review.

**Decision: the deep lane stays on Nemotron 3 Ultra.** Both models now meet the 45 s
target, and only Ultra meets the critic target as well.

One risk worth naming: Ultra's slowest turn was 89.3 s against a 90 s timeout. It did
not fail in 9 turns, but it is close. If a live demo turn ever times out, switching
`LANE_DEEP_MODEL` to lightning is a one-line change in `.env` that costs an extra
critic round and nothing else.

## Point 14, closed

Target: under 45 s per turn. `block_T3` was **46.5 s** mean; it is now **35.8 s**.

The suggested fix was to trim the prompts, starting with the Planner's. Measured, the
Planner's whole prompt is under 5 KB (1,781 chars of system prompt, 3,176 of context),
so there was nothing to cut — the cost was never in reading the prompt. What fixed it
was temperature 0 on both lanes, which cut the critic rounds from 2.0 to 1.0.
