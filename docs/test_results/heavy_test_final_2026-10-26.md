# Heavy test · 2026-10-26T10:33:56+00:00

- Data: **SAMPLE_MODE** · World Model: `meterless-world-model`
- Endpoint: `https://integrate.api.nvidia.com/v1`
- Fast lane: `nvidia/nemotron-3.5-lightning-30b-a3b` · deep lane: `nvidia/nemotron-3-ultra-550b-a55b`
- Runs per scenario: 5

| Scenario | Turns | Clean | Failures | Escalated | Mean ms | Max ms | Critic rounds | False blocks | Re-plan stability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 15 | 15 | 0 | 0 | 32211 | 58563 | 1.0 (max 1) | 0 | - |
| block_T3 | 15 | 15 | 0 | 10 | 28798 | 53812 | 1.0 (max 1) | 0 | - |
| block_T6 | 15 | 15 | 0 | 10 | 33645 | 56953 | 1.0 (max 1) | 0 | - |
| reopen_T6 | 15 | 15 | 0 | 5 | 49515 | 75811 | 1.0 (max 1) | 0 | 64% |

## Latency per agent (mean ms)

| Scenario | critic | explainer | intake | planner | reconciler | risk_analyst |
| --- | --- | --- | --- | --- | --- | --- |
| block_T20 | 6834 | 10138 | 21 | 16482 | 6554 | 2854 |
| block_T3 | 6740 | 11979 | 16 | 9325 | 6001 | 2792 |
| block_T6 | 4540 | 12877 | 19 | 15469 | 7634 | 3125 |
| reopen_T6 | 7693 | 11825 | 33 | 17159 | 8512 | 4055 |

## Failures

None.
