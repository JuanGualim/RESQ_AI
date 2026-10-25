"""Run the demo scenario and save its outputs to output_examples/.

    python scripts/run_demo.py                  # baseline plan, then block T6 and re-plan
    python scripts/run_demo.py --segment T3     # block another segment

Uses whatever .env says (Zetaris or SAMPLE_MODE, World Model service or fallback,
Nightshift or direct NVIDIA). Writes, per step: report (.md), plan (.json) and trace (.jsonl).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from resq import world  # noqa: E402
from resq.config import get_settings  # noqa: E402
from resq.run import execute  # noqa: E402

OUT_DIR = ROOT_DIR / "output_examples"


def save(step: str, result: dict, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{step}_report.md").write_text(result["report"], encoding="utf-8")
    plan = result["plan"].model_dump() if result["plan"] else None
    (out_dir / f"{step}_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    trace_file = get_settings().logs_dir / f"trace_{result['run_id']}.jsonl"
    if trace_file.exists():
        shutil.copy(trace_file, out_dir / f"{step}_trace.jsonl")
    print(f"{step}: plan v{plan['version'] if plan else '-'} · {len(plan['assignments']) if plan else 0} assignments · "
          f"escalated={result['escalated']} · {len(result['trace'])} trace steps")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--segment", default="T6", help="road segment the coordinator blocks (default T6)")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="output folder (default output_examples/)")
    args = parser.parse_args()

    settings = get_settings()
    print(f"data={'SAMPLE_MODE' if settings.sample_mode else 'Zetaris'} · world={world.backend().name} · "
          f"model={settings.lane_model('fast')} @ {settings.model_base_url.split('/')[2] if settings.model_base_url else '-'}")
    world.reset()
    save("01_baseline", execute("How should we distribute aid right now?"), args.out)
    save(f"02_block_{args.segment}", execute("", {"type": "segment_blocked", "id": args.segment, "source": "coordinator"}), args.out)
    save("03_why", execute("Why did the plan change?"), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
