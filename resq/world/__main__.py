"""Inspect the World Model from the command line (what the agents share and how it evolved).

    python -m resq.world summary                         # engine, counts, latest events
    python -m resq.world timeline T7                     # how the belief about T7 evolved, with evidence
    python -m resq.world state --at 2020-11-05T09:00     # segments and shelters as believed at that time
    python -m resq.world audit --last 15                 # the engine's audit log
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from resq import world

STATUS_TABLES = ("road_segments", "shelters")


def summary(_args) -> None:
    backend = world.backend()
    facts, entities = backend.facts(), backend.entities()
    print(f"engine: {backend.name}")
    print(f"entities: {len(entities)} ({', '.join(f'{t} {n}' for t, n in sorted(Counter(e['type'] for e in entities).items()))})")
    print(f"facts: {len(facts)} ({', '.join(f'{p} {n}' for p, n in sorted(Counter(f['predicate'] for f in facts).items()))})")
    plan = world.latest_plan()
    print(f"latest plan: v{plan['version']} · {len(plan['assignments'])} assignments · escalated={plan.get('escalated')}" if plan else "latest plan: none")
    print("latest events:")
    for event in world.history()[-8:]:
        print(f"  #{event['seq']:<4} {event.get('ts', ''):19} {event['type']:26} {event['id']:5} "
              f"{event.get('status') or event.get('risk_level') or ''} ({event.get('source')})")


def timeline(args) -> None:
    rows = world.timeline(args.object_id)
    if not rows:
        print(f"no facts about {args.object_id}")
        return
    for row in rows:
        value = row.get("status") or row.get("risk_level") or ""
        confidence = f"{row['confidence']:.2f}" if isinstance(row.get("confidence"), (int, float)) else "-"
        evidence = ",".join(row.get("evidence", []) or [])
        print(f"#{row['seq']:<4} {row['at']} {row['predicate']:15} {value:13} conf={confidence} "
              f"{row.get('source', ''):11} {row.get('by', ''):12} {evidence}")
        if row.get("reason"):
            print(f"      reason: {row['reason']}")


def state(args) -> None:
    current = world.get_state(as_of=args.at)
    print(f"state as believed at {args.at or 'now'}:")
    for table in STATUS_TABLES:
        for object_id, record in sorted(current.get(table, {}).items()):
            status = record.get("status")
            official = record.get("official_status")
            if status or args.all:
                print(f"  {object_id:5} {status or official or '-':13} conf={record.get('status_confidence') or '-'} "
                      f"evidence={','.join(record.get('status_evidence') or [])}")


def audit(args) -> None:
    for entry in world.audit()[-args.last:]:
        summary = entry["summary"] if len(entry["summary"]) <= 140 else entry["summary"][:139] + "…"
        print(f"#{entry['seq']:<5} {entry['at']:24} {entry['kind']:14} {entry['actor']:14} {summary}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m resq.world", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("summary").set_defaults(run=summary)
    p = commands.add_parser("timeline")
    p.add_argument("object_id")
    p.set_defaults(run=timeline)
    p = commands.add_parser("state")
    p.add_argument("--at", default=None, help="scenario time, e.g. 2020-11-05T09:00")
    p.add_argument("--all", action="store_true", help="also list objects with only their official status")
    p.set_defaults(run=state)
    p = commands.add_parser("audit")
    p.add_argument("--last", type=int, default=20)
    p.set_defaults(run=audit)
    args = parser.parse_args(argv)
    try:
        args.run(args)
    except world.WorldError as error:
        print(f"World Model unavailable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
