"""Build a working BIDS copy of ERP CORE P3 for the gold-standard pipeline.

Like the MMN builder: in ds the target/standard distinction lives in the events `value`
(two digits — tens=block target letter, units=trial stimulus letter; TARGET iff tens==units),
while `trial_type` is "stimulus"/"response". MNE-BIDS-Pipeline keys on `trial_type`, so we
relabel trial_type to {target, standard, response} so both pipelines analyse the identical
target-minus-standard contrast. Signal files (.set/.fdt) are symlinked; nothing original is
modified.

  python tools/benchmark/build_bids_subset_p3.py --n 20 --out ~/mne_data/erpcore_p3_bench_bids
"""
from __future__ import annotations
import argparse, shutil
from pathlib import Path
import pandas as pd

SRC = Path.home() / "mne_data" / "erpcore-P3"
TOP_FILES = ["dataset_description.json", "participants.tsv", "participants.json",
             "task-P3_events.json", "README.txt", "CHANGES", "LICENSE"]


def relabel_events(src_tsv: Path, dst_tsv: Path):
    df = pd.read_csv(src_tsv, sep="\t")
    def lab(v, tt):
        if pd.notna(v) and 11 <= int(v) <= 55:
            return "target" if (int(v) // 10 == int(v) % 10) else "standard"
        return tt
    df["trial_type"] = [lab(v, tt) for v, tt in zip(df["value"], df["trial_type"])]
    df.to_csv(dst_tsv, sep="\t", index=False, na_rep="n/a")


def link_or_copy(src: Path, dst: Path):
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
    ap.add_argument("--out", default=str(Path.home() / "mne_data" / "erpcore_p3_bench_bids"))
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
    print(f"Built P3 BIDS subset: {out}  (N={len(subs)})")


if __name__ == "__main__":
    main()
