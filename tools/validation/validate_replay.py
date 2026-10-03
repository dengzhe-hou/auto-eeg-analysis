"""Exercise captured-code replay on the existing MNE sample regression pipeline.

Uses cached sample data only. Preserves both generated programs and both runs in
--work-dir. Compares the pipeline's exported (rounded) metrics, not all waveforms.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import replay
from regression_pipeline import resolve_raw_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    analysis = work / "study" / "analysis"
    analysis.mkdir(parents=True)
    shutil.copy2(Path(__file__).resolve().parents[1] / "regression_pipeline.py", analysis)
    (analysis / "pipeline.py").write_text(
        "import argparse, json\nfrom pathlib import Path\n"
        "from regression_pipeline import run_pipeline\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--data')\nparser.add_argument('--out')\n"
        "args = parser.parse_args()\n"
        "result = run_pipeline(data_path=args.data, download=False)\n"
        "(Path(args.out) / 'metrics.json').write_text(json.dumps(result, indent=2), encoding='utf-8')\n",
        encoding="utf-8",
    )
    replay.write_json(analysis / "run.json", {"commands": [
        ["{python}", "pipeline.py", "--data", "{data}", "--out", "{out}"]]})
    data = resolve_raw_path(download=False).parents[2]
    bundle = work / "bundle"
    replay.capture(work / "study", data, bundle)
    for name in ("first", "repeat"):
        if replay.run(bundle, work / name):
            raise SystemExit(f"Replay failed: {work / name}")
    first, repeat = [json.loads((work / name / "metrics.json").read_text(encoding="utf-8-sig"))
                     for name in ("first", "repeat")]
    result = {
        "dataset": "cached MNE sample", "source": "tools/regression_pipeline.py",
        "comparison": "Exact equality of exported rounded ERP/cluster metrics and configuration",
        "matched": first == repeat, "first": first, "repeat": repeat,
        "scope": "Same machine and captured environment; not independent user validation",
    }
    replay.write_json(work / "comparison.json", result)
    print(f"Matched: {result['matched']}; record: {work / 'comparison.json'}")
    if not result["matched"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
