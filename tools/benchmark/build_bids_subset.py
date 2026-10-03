"""Build a working BIDS copy of ERP CORE MMN for the gold-standard pipeline.

Why this step exists: in the OpenNeuro ds003065 MMN events.tsv the standard/deviant
distinction lives ONLY in the `value` column (80=standard, 70=deviant, 180=first
stream of standards), while `trial_type` is "stimulus" for every tone. MNE-BIDS-Pipeline
reads conditions from `trial_type`, so we relabel trial_type from value into
{standard, deviant, first} so the gold-standard pipeline analyses the *identical*
contrast AEA's recipe does (deviant=70 vs standard=80, first-stream=180 excluded).

Big signal files (.set/.fdt) are symlinked; only the tiny events.tsv is rewritten.
Nothing in the original dataset is modified.

  python tools/benchmark/build_bids_subset.py --n 40 --out ~/mne_data/erpcore_mmn_bench_bids
"""
from __future__ import annotations
import argparse, shutil
from pathlib import Path
import pandas as pd

SRC = Path.home() / "mne_data" / "MNE-erpcoremmn2021-data"
VALUE_TO_TRIALTYPE = {80: "standard", 70: "deviant", 180: "first"}
TOP_FILES = ["dataset_description.json", "participants.tsv", "participants.json",
             "task-MMN_events.json", "README.txt", "CHANGES", "LICENSE"]


def relabel_events(src_tsv: Path, dst_tsv: Path):
    df = pd.read_csv(src_tsv, sep="\t")
    df["trial_type"] = [VALUE_TO_TRIALTYPE.get(int(v), tt) if pd.notna(v) else tt
                        for v, tt in zip(df["value"], df["trial_type"])]
    df.to_csv(dst_tsv, sep="\t", index=False, na_rep="n/a")


def link_or_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    # symlink the big binaries, copy the small sidecars
    if src.suffix in {".fdt", ".set"}:
        dst.symlink_to(src.resolve())
    else:
        shutil.copy2(src, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--out", default=str(Path.home() / "mne_data" / "erpcore_mmn_bench_bids"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for f in TOP_FILES:
        if (SRC / f).exists():
            shutil.copy2(SRC / f, out / f)

    subs = sorted(p.name for p in SRC.glob("sub-*"))[: args.n]
    for sub in subs:
        seeg = SRC / sub / "eeg"
        deeg = out / sub / "eeg"
        for f in seeg.iterdir():
            if f.name.endswith("_events.tsv"):
                deeg.mkdir(parents=True, exist_ok=True)
                relabel_events(f, deeg / f.name)
            else:
                link_or_copy(f, deeg / f.name)
        print(f"  {sub}: linked + events relabeled", flush=True)
    print(f"Built BIDS subset: {out}  (N={len(subs)})")


if __name__ == "__main__":
    main()
