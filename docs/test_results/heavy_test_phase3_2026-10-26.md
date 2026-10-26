# Heavy test · 2026-10-26T07:56:13+00:00

- Data: **SAMPLE_MODE** · World Model: `meterless-world-model`
- Endpoint: `https://integrate.api.nvidia.com/v1`
- Fast lane: `nvidia/nemotron-3.5-lightning-30b-a3b` · deep lane: `nvidia/nemotron-3-ultra-550b-a55b`
- Runs per scenario: 10

| Scenario | Turns | Clean | Failures | Escalated | Mean ms | Max ms | Critic rounds | False blocks | Re-plan stability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 30 | 30 | 0 | 0 | 33409 | 116703 | 1.0 (max 1) | 0 | - |
| block_T3 | 30 | 30 | 0 | 20 | 42864 | 120827 | 1.0 (max 1) | 10 | - |
| block_T6 | 30 | 30 | 0 | 20 | 57253 | 171046 | 1.0 (max 1) | 10 | - |
| reopen_T6 | 30 | 23 | 7 | 10 | 58376 | 115079 | 1.0 (max 1) | 9 | 49% |

## Latency per agent (mean ms)

| Scenario | critic | explainer | intake | planner | reconciler | risk_analyst |
| --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 4375 | 14694 | 22 | 12441 | 6750 | 4096 |
| block_T3 | 16057 | 9695 | 21 | 23584 | 6933 | 2781 |
| block_T6 | 21251 | 13914 | 18 | 27461 | 6927 | 8989 |
| reopen_T6 | 9087 | 11040 | 27 | 24956 | 9429 | 3588 |

## Failures

- **reopen_T6** · reopen · `quality` — after reopening, only 47% of the lines match the plan plan
- **reopen_T6** · reopen · `quality` — after reopening, only 47% of the lines match the plan plan
- **reopen_T6** · reopen · `quality` — after reopening, only 45% of the lines match the plan plan
- **reopen_T6** · reopen · `quality` — after reopening, only 45% of the lines match the plan plan
- **reopen_T6** · reopen · `quality` — after reopening, only 45% of the lines match the plan plan
- **reopen_T6** · reopen · `quality` — after reopening, only 47% of the lines match the plan plan
- **reopen_T6** · reopen · `quality` — after reopening, only 45% of the lines match the plan plan
