# Input examples

Questions and coordinator events the system understands. Run each with `python -m resq.run`.

| Input | Command | Request type | What happens |
| --- | --- | --- | --- |
| "How should we distribute aid right now?" | `python -m resq.run --question "How should we distribute aid right now?"` | `plan` | Full graph: reconcile reports, assess risk, plan, critic loop, report (plan v1) |
| Block a road segment | `python -m resq.run --event block:T6` | `event` | The block is stored in the World Model; the graph re-plans (plan v2) and explains what changed |
| Reopen a road segment | `python -m resq.run --event reopen:T6` | `event` | Same, with the segment open again |
| "Why did the plan change?" | `python -m resq.run --question "Why did the plan change?"` | `why` | No re-plan: explains the latest plan and the events behind it |
| "What is the current situation?" | `python -m resq.run --question "What is the current situation?"` | `situation` | Reconcile + risk, then a situation report without a plan |

Good segments to block in the demo: `T6` (main paved road to the river valley; leaves only fording vehicles able to reach it), `T3` (the town center's road to the east), `T20` (the dry route to El Zapotal).

Start from a clean World Model with `python -m resq.run --reset`.
