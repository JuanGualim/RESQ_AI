# Heavy test · 2026-10-25

Two batteries of `scripts/heavy_test.py`, run on Harry's Windows machine. Full
per-run JSON stays in `logs/` (not in git); this is the summary.

Both batteries ran on `SAMPLE_MODE=true`: Zetaris is reachable over Tailscale and
answers SQL, but the scenario tables are not registered yet, so every
`SELECT ... FROM resq_pg.<table>` returns `TABLE_OR_VIEW_NOT_FOUND`. A battery on
Zetaris data is blocked on that registration.

The World Model ran as the real Node service on `:4380` (conformance 8/8) in both.

## 1. Baseline — direct NVIDIA, before the agent fixes

- Endpoint: `https://integrate.api.nvidia.com/v1`
- Both lanes: `nvidia/nemotron-3.5-lightning-30b-a3b`
- Scenarios: baseline, block T6, block T3 · 5 runs each · **35 turns, 0 failures**

| Scenario | Turns | Escalated | Mean ms | Median ms | Max ms | Critic rounds (plan) |
| --- | --- | --- | --- | --- | --- | --- |
| baseline | 5 | 0 | 42,044 | 32,547 | 64,875 | 2.0 (max 2) |
| block_T3 | 15 | 10 | 23,441 | 28,562 | 50,155 | 2.0 (max 3) |
| block_T6 | 15 | 10 | 21,607 | 23,719 | 37,452 | 2.0 (max 2) |

Mean ms per agent, block_T6: critic 5,588 · explainer 6,517 · planner 9,415 ·
reconciler 4,909 · risk_analyst 2,338 · intake 25.

## 2. After the fixes — Meterless Nightshift

- Endpoint: `http://127.0.0.1:8088/v1` (Nightshift runtime on this machine)
- Fast lane: `nvidia/nemotron-3.5-lightning-30b-a3b`
- Deep lane: `nvidia/nemotron-3-ultra-550b-a55b`
- Scenarios: block T6, block T3, block T20 · 5 runs each · **45 turns, 0 failures**

| Scenario | Turns | Escalated | Mean ms | Median ms | Max ms | Critic rounds (plan) |
| --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 15 | 0 | 27,186 | 28,843 | 50,907 | **1.0** (max 1) |
| block_T3 | 15 | 10 | 46,453 | 35,296 | 129,375 | **1.2** (max 2) |
| block_T6 | 15 | 9 | 32,172 | 25,484 | 76,187 | **1.0** (max 1) |

Mean ms per agent:

| Scenario | critic | explainer | planner | reconciler | risk_analyst | intake |
| --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 8,706 | 6,395 | 14,258 | 5,090 | 2,640 | 27 |
| block_T3 | **26,450** | 5,441 | 25,403 | 5,445 | 3,743 | 25 |
| block_T6 | 5,067 | 6,599 | 11,979 | 5,825 | 7,582 | 17 |

## What the numbers say

**Point 13 — critic false positives: met.** Giving the reason review its own
`stock_cuts` field took the base plan from **2.0 critic rounds to 1.0**. The
Critic was treating coverage lost to an empty warehouse as a priority inversion,
so it sent back plans that were already correct. Target was at most one review on
the base plan.

**Point 14 — latency under 45 s: not met for block_T3 (46.5 s mean).** The
suggested fix was to trim the prompts, starting with the Planner. Measured, that
is not where the time goes:

```
planner system prompt :   1,781 chars
planner user context  :   3,176 chars  (~794 tokens)
  communities            2,272 chars   (9 communities)
  scarcity                 438 chars
  total_stock              277 chars
  fleet                     60 chars
```

Under 5 KB in total, so there is nothing meaningful to cut — the cost is in
generation, not in reading the prompt. The actual outlier is the **Critic at
26,450 ms mean on block_T3, against 5,067 ms on block_T6** with the same prompt
and the same number of rounds. Both run on the deep lane, which in this battery
was Nemotron 3 Ultra (550B). The likely cause is the deep model's own speed under
a longer plan, not the prompt size.

Next step, to be measured rather than assumed: run the same battery with the deep
lane on `nemotron-3.5-lightning` and compare. If the Critic drops to single-digit
seconds with no loss in review quality, split the lanes — Ultra for the Planner's
judgment, lightning for the Critic's review.

**Escalations are consistent with the data**, not noise: blocking T6 or T3 makes
the P5.2 critical minimum infeasible (the fording fleet cannot carry it), so those
turns escalate by design. Blocking T20 does not, and it never escalated.

## Still open

- A battery on Zetaris data (`SAMPLE_MODE=false`), once the scenario tables exist.
- The phase 3 battery: 3 scenarios x 10 runs plus the block-and-reopen scenario.
- The deep-lane comparison described above.
