# Heavy test · 2026-10-26T09:52:04+00:00

- Data: **SAMPLE_MODE** · World Model: `meterless-world-model`
- Endpoint: `https://integrate.api.nvidia.com/v1`
- Fast lane: `nvidia/nemotron-3.5-lightning-30b-a3b` · deep lane: `nvidia/nemotron-3-ultra-550b-a55b`
- Runs per scenario: 5

| Scenario | Turns | Clean | Failures | Escalated | Mean ms | Max ms | Critic rounds | False blocks | Re-plan stability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 15 | 15 | 0 | 0 | 30505 | 50156 | 1.0 (max 1) | 0 | - |
| block_T3 | 15 | 15 | 0 | 10 | 41189 | 77828 | 1.0 (max 1) | 2 | - |
| block_T6 | 15 | 15 | 0 | 10 | 38654 | 70953 | 1.2 (max 2) | 4 | - |
| reopen_T6 | 15 | 10 | 5 | 5 | 38897 | 62500 | 1.0 (max 1) | 0 | 51% |

## Latency per agent (mean ms)

| Scenario | critic | explainer | intake | planner | reconciler | risk_analyst |
| --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 4616 | 10792 | 19 | 13218 | 8554 | 2789 |
| block_T3 | 11842 | 14525 | 22 | 15960 | 8363 | 3440 |
| block_T6 | 10919 | 13037 | 19 | 17783 | 5864 | 3434 |
| reopen_T6 | 6665 | 8668 | 32 | 14352 | 5469 | 3478 |

## Failures

- **reopen_T6** · reopen · `quality` — after reopening, C01 was served in the baseline and is unserved now; after reopening, C08 was served in the baseline and is unserved now; after reopening, C11 was served in the baseline and is unserved now
- **reopen_T6** · reopen · `quality` — after reopening, C01 was served in the baseline and is unserved now; after reopening, C08 was served in the baseline and is unserved now; after reopening, C11 was served in the baseline and is unserved now
- **reopen_T6** · reopen · `quality` — after reopening, C01 was served in the baseline and is unserved now; after reopening, C08 was served in the baseline and is unserved now; after reopening, C11 was served in the baseline and is unserved now
- **reopen_T6** · reopen · `quality` — after reopening, C01 was served in the baseline and is unserved now; after reopening, C08 was served in the baseline and is unserved now; after reopening, C11 was served in the baseline and is unserved now
- **reopen_T6** · reopen · `quality` — after reopening, C01 was served in the baseline and is unserved now; after reopening, C08 was served in the baseline and is unserved now; after reopening, C11 was served in the baseline and is unserved now
