#!/usr/bin/env python
"""Export the exact input of the second-level cluster test, so another toolbox can rerun it.

The cluster-permutation p-value is the number every AEA recipe's conclusion rests on, and it had
never been checked against a second implementation -- `tools/env/backends.json` says so in as many
words (`stats.cluster_permutation` / fieldtrip / `measured: false`).

Certifying it needs more care than certifying an amplitude, because two things could differ and
only one of them is interesting:

  * the ADJACENCY GRAPH. MNE builds channel adjacency by Delaunay triangulation of the montage;
    FieldTrip builds it from `cfg.neighbours`, by its own triangulation or a distance rule. Letting
    each toolbox pick its own would measure the montage geometry, not the test. So the adjacency is
    computed once here and exported, and both sides cluster over the identical graph.
  * the PERMUTATION SCHEME. This one is the actual subject of the comparison.

Writes a .mat that FieldTrip can load directly.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "validation"))

COMPONENTS = {
    "MMN":  ("validate_mmn_group",          "subject_mmn",  "MNE-erpcoremmn2021-data"),
    "P3":   ("validate_p3_group",           "subject_p3",   "erpcore-P3"),
    "N170": ("validate_n170_erpcore_group", "subject_n170", "erpcore-N170"),
    "N400": ("validate_n400_erpcore_group", "subject_n400", "erpcore-N400"),
    "ERN":  ("validate_ern_erpcore_group",  "subject_ern",  "erpcore-ERN"),
}


def main() -> int:
    import mne
    from scipy.io import savemat
    mne.set_log_level("ERROR")

    ap = argparse.ArgumentParser()
    ap.add_argument("--component", default="MMN", choices=sorted(COMPONENTS))
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--out", type=Path, default=Path("tools/benchmark/cluster_cert"))
    args = ap.parse_args()

    mod_name, fn_name, data_dir = COMPONENTS[args.component]
    mod = __import__(mod_name)
    subject_fn = getattr(mod, fn_name)
    data = Path.home() / "mne_data" / data_dir

    diffs, subs, info_ref, times_ref = [], [], None, None
    for sub in sorted(p.name for p in data.glob("sub-*"))[: args.subjects]:
        try:
            res = subject_fn(sub)
        except Exception as e:                                  # noqa: BLE001
            print(f"  {sub}: SKIP {type(e).__name__}", flush=True)
            continue
        # every validate_* returns the difference Evoked first or second; find it
        diff = next(x for x in (res if isinstance(res, tuple) else (res,))
                    if hasattr(x, "data") and hasattr(x, "times"))
        diffs.append(diff.data)
        subs.append(sub)
        if info_ref is None:
            info_ref, times_ref = diff.info, diff.times
        print(f"  {sub}: ok", flush=True)

    X = np.array(diffs)                                          # (n_subj, n_chan, n_time)
    print(f"\n{args.component}: {X.shape[0]} subjects x {X.shape[1]} channels x {X.shape[2]} samples")

    # One adjacency, used by BOTH toolboxes.
    adjacency, ch_names = mne.channels.find_ch_adjacency(info_ref, ch_type="eeg")
    A = np.asarray(adjacency.todense()).astype(np.uint8)
    np.fill_diagonal(A, 0)
    print(f"adjacency: {A.shape[0]} channels, {int(A.sum() // 2)} undirected edges")

    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.out / f"cluster_input_{args.component}"
    savemat(str(stem) + ".mat", {
        "X": np.transpose(X, (1, 2, 0)),        # FieldTrip wants chan x time x subject
        "times": times_ref,
        "labels": np.array(ch_names, dtype=object),
        "adjacency": A,
        "component": args.component,
    })
    (stem.with_suffix(".json")).write_text(json.dumps({
        "component": args.component, "subjects": subs,
        "n_subjects": len(subs), "n_channels": int(X.shape[1]), "n_times": int(X.shape[2]),
        "n_adjacency_edges": int(A.sum() // 2), "ch_names": list(ch_names),
        "tmin_s": float(times_ref[0]), "tmax_s": float(times_ref[-1]),
        "sfreq_hz": float(1.0 / np.median(np.diff(times_ref))),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {stem}.mat and {stem}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
