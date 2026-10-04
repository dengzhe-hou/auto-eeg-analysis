"""Prepare the MNE sample raw, preprocessed, ICA-cleaned and epoched inputs.

Run: conda run -n aeais python tools/prepare_sample_case.py
The preparation settings match the archived sample case study. Preparation stops
after saving epochs; ERP contrasts, figures and findings are separate analyses.
"""
import argparse
import json
import os
from pathlib import Path


SEED = 42


def prepare(project: Path):
    import mne

    mne.set_log_level("WARNING")
    PROJECT = project

    # Reuse the configured MNE sample cache, fetching the dataset if absent.
    raw_link = PROJECT / "raw" / "sub-01.fif"
    if not raw_link.exists():
        raw_link.parent.mkdir(parents=True, exist_ok=True)
        sample_raw = Path(mne.datasets.sample.data_path()) / "MEG" / "sample" / "sample_audvis_raw.fif"
        os.symlink(sample_raw, raw_link)
        print(f"=== BOOTSTRAP === linked sample data -> {raw_link}", flush=True)

    pp_path = PROJECT / "preprocess-stage" / "sub-01" / "sub-01_preprocessed_raw.fif"
    if not pp_path.exists():
        print("=== PREPROCESS (bootstrap) ===", flush=True)
        pp_path.parent.mkdir(parents=True, exist_ok=True)
        raw_bs = mne.io.read_raw_fif(raw_link, preload=True)
        raw_bs.pick_types(meg=False, eeg=True, exclude="bads")
        raw_bs.filter(l_freq=0.1, h_freq=40.0, n_jobs=1)
        raw_bs.set_eeg_reference("average", projection=False)
        raw_bs.save(pp_path, overwrite=True)
        json.dump({"bandpass": [0.1, 40], "reference": "average",
                   "n_ch": raw_bs.info["nchan"], "sfreq": raw_bs.info["sfreq"]},
                  open(pp_path.parent / "preprocess_summary.json", "w", encoding="utf-8"), indent=2)
        print(f"  Preprocessed -> {pp_path} ({raw_bs.info['nchan']} EEG ch, 0.1-40 Hz, avg ref)", flush=True)

    # === ICA ===
    print("=== ICA ===", flush=True)
    ica_dir = PROJECT / "ica-stage" / "sub-01"
    ica_dir.mkdir(parents=True, exist_ok=True)
    raw_pp = mne.io.read_raw_fif(PROJECT / "preprocess-stage/sub-01/sub-01_preprocessed_raw.fif", preload=True)
    raw_hp = raw_pp.copy().filter(l_freq=1.0, h_freq=None)
    ica = mne.preprocessing.ICA(n_components=15, method="infomax", random_state=SEED,
                                 max_iter="auto", fit_params=dict(extended=True))
    ica.fit(raw_hp)
    print(f"  Fit {ica.n_components_} components", flush=True)

    from mne_icalabel import label_components
    labels = label_components(raw_hp, ica, method="iclabel")
    label_list = labels["labels"]
    exclude = [i for i, l in enumerate(label_list) if l in {"eye blink", "muscle artifact", "heart beat"}]
    ica.exclude = exclude
    print(f"  ICLabel: {list(enumerate(label_list))}", flush=True)
    print(f"  Excluding: {exclude}", flush=True)

    raw_clean = raw_pp.copy()
    ica.apply(raw_clean)
    ica_path = ica_dir / "sub-01_ica-cleaned_raw.fif"
    raw_clean.save(ica_path, overwrite=True)
    json.dump({"excluded": exclude, "labels": label_list, "seed": SEED},
              open(ica_dir / "ica_summary.json", "w", encoding="utf-8"), indent=2)
    print(f"  Saved: {ica_path}", flush=True)

    # === EPOCH ===
    print("\n=== EPOCH ===", flush=True)
    epoch_dir = PROJECT / "epoch-stage" / "sub-01"
    epoch_dir.mkdir(parents=True, exist_ok=True)

    raw_orig = mne.io.read_raw_fif(PROJECT / "raw/sub-01.fif", preload=False)
    events = mne.find_events(raw_orig, stim_channel="STI 014", shortest_event=1)
    event_id = {"auditory/left": 1, "auditory/right": 2, "visual/left": 3, "visual/right": 4}

    epochs = mne.Epochs(raw_clean, events, event_id=event_id,
                         tmin=-0.2, tmax=0.5, baseline=(-0.2, 0),
                         preload=True, reject=dict(eeg=150e-6))
    per_cond = {k: len(epochs[k]) for k in event_id}
    print(f"  {len(epochs)} epochs: {per_cond}", flush=True)
    epochs.save(epoch_dir / "sub-01-epo.fif", overwrite=True)
    json.dump({"n_epochs": len(epochs), "per_cond": per_cond},
              open(epoch_dir / "epoch_summary.json", "w", encoding="utf-8"), indent=2)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=Path("projects/mne-sample-audvis"),
                    help="project directory for the prepared sample inputs")
    args = ap.parse_args()
    prepare(args.project)


if __name__ == "__main__":
    main()
