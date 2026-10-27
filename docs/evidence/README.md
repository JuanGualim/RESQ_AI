# Evidence: RESQ AI runs on Meterless Nightshift with NVIDIA Nemotron

Captured on 2026-10-27 on the Nightshift host (Harry's Windows machine), straight
after `python scripts/run_demo.py` ran the full demo on Zetaris data. No API keys or
tokens are visible in any screenshot.

Nightshift serves the OpenAI-compatible API at `http://127.0.0.1:8088/v1`; RESQ AI
reaches it through `resq/llm.py`, which sends the `meterless-app: resq-ai` header
(AGENTS.md §2 rule 2).

## `nightshift-apps-resq-ai.png` — Console → Apps

Nightshift identifies our client: **Resq Ai**, "named via meterless-app header",
**15 requests**, last seen 2 minutes earlier, on **`nvidia/nemotron-3…`**. This is the
app registration that proves the calls come from this project and not from a
generic client.

## `nightshift-proof-receipts.png` — Console → Proof

Signed receipts, one per request. Each row reads **`resq-ai`** against
**Nemotron 3.5 Lightning 30B A3B**, with the input and output token counts, and the
receipt is **signed by `meterlessd` (Ed25519)**. The panel below shows the request
plan and the route taken for the last call.

## `nightshift-console-overview.webp` — the whole window

The NIGHT view with the Console open, so the two are visibly the same running
instance. The status bar reads `RUNTIME :8088 · reqs 15 · tok 58.7k`.

## The same run, from our side

`python -m resq.llm --check` on this machine, same session:

```text
PASS  provider                     Meterless Nightshift at 127.0.0.1:8088
PASS  meterless primary provider   requests go through Nightshift
PASS  connection + authorization   GET /v1/models answered
PASS  model discovery              75 models, e.g. meterless/auto, meterless/fast, meterless/deep
PASS  fast lane model              nvidia/nemotron-3.5-lightning-30b-a3b
PASS  fast lane request            nvidia/nemotron-3.5-lightning-30b-a3b answered in 406 ms
PASS  deep lane model              nvidia/nemotron-3-ultra-550b-a55b
PASS  deep lane request            nvidia/nemotron-3-ultra-550b-a55b answered in 1140 ms
```

And the JSONL trace of the published run records the model behind every agent
(`output_examples/01_baseline_trace.jsonl`):

```text
reconciler   [fast]       -> nvidia/nemotron-3.5-lightning-30b-a3b
risk_analyst [fast]       -> nvidia/nemotron-3.5-lightning-30b-a3b
planner      [deep]       -> nvidia/nemotron-3-ultra-550b-a55b
critic       [code+deep]  -> nvidia/nemotron-3-ultra-550b-a55b
explainer    [fast]       -> nvidia/nemotron-3.5-lightning-30b-a3b
```

Both lanes are pinned to NVIDIA Nemotron through `LANE_FAST_MODEL` and
`LANE_DEEP_MODEL`, so no request is routed to a non-NVIDIA model.

## Note on one banner

The Console shows "Runtime endpoint is offline — external apps can't reach the
router" and a suggestion to run `sudo systemctl start meterlessd`. That hint is a
Linux one shown on Windows; the endpoint was serving throughout, as the 15 receipts
and the passing provider check above show.
