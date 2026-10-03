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
import shlex
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
    ap.add_argument("--bundle", type=Path, help="saved tools/replay.py bundle for this run")
    ap.add_argument("--claim", action="append", default=[], help="repeatable; one claim line")
    ap.add_argument("--seed", action="append", default=[], help="repeatable; STAGE=VALUE")
    ap.add_argument("--extra-hash", action="append", default=[], help="repeatable; extra file paths to hash")
    args = ap.parse_args()
    if args.bundle and args.reproduce:
        ap.error("choose --bundle or --reproduce")

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
    setup = ["conda env create -f environment.yml && conda activate aeais",
             "pip install -r requirements-optional.txt   # complexity/specparam/microstate extras",
             "bash tools/env/check_env.sh"]
    python_version = platform.python_version()
    os_version = f"{platform.system()} {platform.release()}"
    versions = {name: pkg_version(name) for name in (
        "mne", "mne_icalabel", "pycrostates", "antropy", "specparam", "sklearn", "numpy", "scipy")}
    if args.bundle:
        # Validate the supplied record rather than writing a receipt for an absent bundle.
        import json
        saved = json.loads((args.bundle / "capture.json").read_text(encoding="utf-8-sig"))
        git_sha = saved["aea_commit"]
        python_version = saved["python"]
        os_version = f"{saved['system']} {saved['machine']} (captured)"
        distributions = {"mne_icalabel": "mne-icalabel", "sklearn": "scikit-learn"}
        versions = {name: saved["packages"].get(distributions.get(name, name), "not recorded")
                    for name in versions}
        setup = [
            "conda env create -n study-replay -f " + shlex.quote(str(args.bundle / "environment.yml")),
            "conda activate study-replay",
        ]
        reproduce = (
            f"# Saved analysis bundle: {args.bundle}\n"
            f"# Captured AEA commit: {saved['aea_commit']}\n"
            "# Transfer this bundle separately; use --data if the data location changed.\n"
            "python tools/replay.py run --bundle " + shlex.quote(str(args.bundle))
            + " --out " + shlex.quote(str(project / "results" / "replay"))
        )

    lines = [
        f"# REPRO_RECEIPT — {name}",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## AEA version",
        f"- Commit: `{git_sha}`",
        "",
        "## Environment (captured bundle)" if args.bundle else "## Environment (introspected)",
        f"- Python: {python_version}  ·  OS: {os_version}",
        f"- MNE-Python: {versions['mne']}  ·  mne-icalabel: {versions['mne_icalabel']}  ·  pycrostates: {versions['pycrostates']}",
        f"- antropy: {versions['antropy']}  ·  specparam: {versions['specparam']}  ·  scikit-learn: {versions['sklearn']}",
        f"- NumPy: {versions['numpy']}  ·  SciPy: {versions['scipy']}",
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
              "cd auto-eeg-analysis",
              f"git checkout {git_sha}",
              *setup, reproduce, "```", ""]

    out = project / "report-stage" / "REPRO_RECEIPT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {out}  ({len(hashes)} files hashed)")


if __name__ == "__main__":
    main()
