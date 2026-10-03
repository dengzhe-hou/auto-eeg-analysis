"""Generate a REPRO_RECEIPT.md for an AEA project.

General, project-parameterized: hashes the project's artifacts, records the git
commit + introspected package versions + seeds, and writes a reproduce block.

  python tools/gen_receipt.py                                  # default mne-sample-audvis
  python tools/gen_receipt.py --project projects/eegbci-resting \
      --reproduce "python tools/validation/validate_resting_recipes.py --subjects 20" \
      --claim "EC>EO posterior alpha (cluster p=0.0002)" \
      --claim "EO>EC complexity (LZC p=4e-5)" \
      --claim "4 microstate maps, GEV 0.66, dur 103ms" \
      --seed ICA=42 --seed ModKMeans=42 --seed cluster=42 --extra-hash tools/validation/resting_results.json
"""
import argparse
import hashlib
import importlib
import platform
import subprocess
from datetime import datetime
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def pkg_version(mod: str) -> str:
    try:
        return importlib.import_module(mod).__version__
    except Exception:
        return "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="projects/mne-sample-audvis")
    ap.add_argument("--reproduce", default=None, help="reproduce command line for the receipt")
    ap.add_argument("--claim", action="append", default=[], help="repeatable; one claim line")
    ap.add_argument("--seed", action="append", default=[], help="repeatable; STAGE=VALUE")
    ap.add_argument("--extra-hash", action="append", default=[], help="repeatable; extra file paths to hash")
    args = ap.parse_args()

    project = Path(args.project)
    name = project.name
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()

    hashes = {}
    for ext in ("*.fif", "*.png", "*.svg", "*.h5", "*.json"):
        for f in sorted(project.rglob(ext)):
            hashes[str(f.relative_to(project))] = sha256(f)
    for extra in args.extra_hash:
        p = Path(extra)
        if p.exists():
            hashes[str(p)] = sha256(p)

    seeds = args.seed or ["ICA=42", "cluster permutation=42"]
    claims = args.claim or ["see ANALYSIS_PLAN.md"]
    reproduce = args.reproduce or (
        "conda env create -f environment.yml && conda activate aeais\n"
        "bash tools/env/check_env.sh\npython tools/run_case_study.py")

    lines = [
        f"# REPRO_RECEIPT — {name}",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## AEA version",
        f"- Commit: `{git_sha}`",
        "",
        "## Environment (introspected)",
        f"- Python: {platform.python_version()}  ·  OS: {platform.system()} {platform.release()}",
        f"- MNE-Python: {pkg_version('mne')}  ·  mne-icalabel: {pkg_version('mne_icalabel')}  ·  pycrostates: {pkg_version('pycrostates')}",
        f"- antropy: {pkg_version('antropy')}  ·  specparam: {pkg_version('specparam')}  ·  scikit-learn: {pkg_version('sklearn')}",
        f"- NumPy: {pkg_version('numpy')}  ·  SciPy: {pkg_version('scipy')}",
        "",
        "## RNG seeds",
        "| Stage | Seed |",
        "|-------|------|",
    ]
    for s in seeds:
        stage, _, val = s.partition("=")
        lines.append(f"| {stage} | {val or 'n/a'} |")
    lines += ["", "## Claims", *[f"- {c}" for c in claims], "",
              "## File hashes (SHA256 prefix)", "| File | Hash |", "|------|------|"]
    for path, h in sorted(hashes.items()):
        lines.append(f"| `{path}` | `{h}` |")
    lines += ["", "## How to reproduce", "```bash",
              "git clone https://github.com/dengzhe-hou/auto-eeg-analysis",
              f"git checkout {git_sha}",
              "conda env create -f environment.yml && conda activate aeais",
              "pip install -r requirements-optional.txt   # complexity/specparam/microstate extras",
              "bash tools/env/check_env.sh", reproduce, "```", ""]

    out = project / "report-stage" / "REPRO_RECEIPT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {out}  ({len(hashes)} files hashed)")


if __name__ == "__main__":
    main()
