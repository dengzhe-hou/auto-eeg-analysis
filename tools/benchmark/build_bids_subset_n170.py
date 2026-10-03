"""Build a working BIDS copy of ERP CORE N170 for the gold-standard pipeline.

Relabel events `trial_type` from `value` so MNE-BIDS-Pipeline (which keys on trial_type)
analyses the identical face-vs-car contrast: value 1-40 -> face, 41-80 -> car,
101-180 -> scrambled, 201/202 -> response. Signal files symlinked; originals untouched.

  python tools/benchmark/build_bids_subset_n170.py --n 20 --out ~/mne_data/erpcore_n170_bench_bids
"""
from __future__ import annotations
import argparse, shutil
from pathlib import Path
import pandas as pd

SRC = Path.home() / "mne_data" / "erpcore-N170"
TOP_FILES = ["dataset_description.json", "participants.tsv", "participants.json",
             "task-N170_events.json", "README.txt", "CHANGES", "LICENSE"]


def _lab(v, tt):
    if pd.isna(v):
        return tt
    v = int(v)
    if 1 <= v <= 40:
        return "face"
    if 41 <= v <= 80:
        return "car"
    if 101 <= v <= 180:
        return "scrambled"
    return tt


def relabel_events(src_tsv, dst_tsv):
    df = pd.read_csv(src_tsv, sep="\t")
    df["trial_type"] = [_lab(v, tt) for v, tt in zip(df["value"], df["trial_type"])]
    df.to_csv(dst_tsv, sep="\t", index=False, na_rep="n/a")


def link_or_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if src.suffix in {".fdt", ".set"}:
        dst.symlink_to(src.resolve())
    else:
        shutil.copy2(src, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default=str(Path.home() / "mne_data" / "erpcore_n170_bench_bids"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in TOP_FILES:
        if (SRC / f).exists():
            shutil.copy2(SRC / f, out / f)
    subs = sorted(p.name for p in SRC.glob("sub-*"))[: args.n]
    for sub in subs:
        seeg, deeg = SRC / sub / "eeg", out / sub / "eeg"
        for f in seeg.iterdir():
            if f.name.endswith("_events.tsv"):
                deeg.mkdir(parents=True, exist_ok=True)
                relabel_events(f, deeg / f.name)
            else:
                link_or_copy(f, deeg / f.name)
        print(f"  {sub}: linked + events relabeled", flush=True)
    print(f"Built N170 BIDS subset: {out}  (N={len(subs)})")


if __name__ == "__main__":
    main()
