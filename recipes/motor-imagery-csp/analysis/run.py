"""Evaluate a fixed CSP/LDA model on unseen recording runs within each person."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import time

import matplotlib
import matplotlib.pyplot as plt
import mne
from mne.decoding import CSP
import numpy as np
import pandas as pd
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from sklearn.pipeline import make_pipeline


matplotlib.use("Agg")
CONFIG = json.loads((Path(__file__).parent / "config.json").read_text())


def load_run(data, subject, run):
    path = data / f"S{subject:03d}" / f"S{subject:03d}R{run:02d}.edf"
    raw = mne.io.read_raw_edf(path, preload=True, verbose=False)
    mne.datasets.eegbci.standardize(raw)
    assert len(raw.ch_names) == 64 and raw.info["sfreq"] == 160
    raw.set_montage("standard_1005")
    raw.filter(*CONFIG["bandpass_hz"], fir_design="firwin", phase="zero", verbose=False)
    raw.notch_filter(CONFIG["notch_hz"], fir_design="firwin", phase="zero", verbose=False)
    raw.set_eeg_reference("average", projection=False, verbose=False)
    events, _ = mne.events_from_annotations(raw, event_id={"T1": 1, "T2": 2}, verbose=False)
    epochs = mne.Epochs(raw, events, event_id={"left": 1, "right": 2},
                        tmin=CONFIG["epoch_s"][0], tmax=CONFIG["epoch_s"][1],
                        baseline=None, proj=False, preload=True, reject=None,
                        reject_by_annotation=True, verbose=False)
    metadata = {
        "subject": subject, "run": run, "sfreq": float(raw.info["sfreq"]),
        "channels": raw.ch_names, "event_count": len(events),
        "retained": len(epochs), "left": int(sum(epochs.events[:, 2] == 1)),
        "right": int(sum(epochs.events[:, 2] == 2)),
        "dropped": [{"event_index": i, "reason": list(reason)}
                    for i, reason in enumerate(epochs.drop_log) if reason],
        "source_bytes": path.stat().st_size,
    }
    assert metadata["left"] > 0 and metadata["right"] > 0
    return epochs.get_data(), epochs.events[:, 2] - 1, epochs.events[:, 0], metadata


def evaluate_subject(data, subject):
    runs = {r: load_run(data, subject, r) for r in CONFIG["runs"]}
    folds, predictions = [], []
    for held_out in CONFIG["runs"]:
        train_runs = [r for r in CONFIG["runs"] if r != held_out]
        x_train = np.concatenate([runs[r][0] for r in train_runs])
        y_train = np.concatenate([runs[r][1] for r in train_runs])
        x_test, y_test, samples, _ = runs[held_out]
        model = make_pipeline(CSP(**CONFIG["csp"]), LinearDiscriminantAnalysis(solver="svd"))
        model.fit(x_train, y_train)
        predicted = model.predict(x_test)
        probabilities = model.predict_proba(x_test)[:, 1]
        csp = model.named_steps["csp"]
        projected = np.einsum("kc,nct->nkt", csp.filters_[:CONFIG["csp"]["n_components"]], x_test)
        manual = np.log(np.mean(projected ** 2, axis=2))
        feature_error = float(np.max(np.abs(manual - csp.transform(x_test))))
        np.testing.assert_allclose(manual, csp.transform(x_test), atol=1e-10, rtol=0)
        folds.append({"subject": subject, "held_out_run": held_out, "train_runs": train_runs,
                      "train_n": len(y_train), "test_n": len(y_test),
                      "balanced_accuracy": float(balanced_accuracy_score(y_test, predicted)),
                      "confusion_matrix": confusion_matrix(y_test, predicted, labels=[0, 1]).tolist(),
                      "manual_feature_max_error": feature_error})
        predictions.extend({"subject": subject, "run": held_out, "event_sample": int(sample),
                            "label": int(label), "prediction": int(prediction),
                            "right_probability": float(probability)}
                           for sample, label, prediction, probability
                           in zip(samples, y_test, predicted, probabilities, strict=True))
    return {"subject": subject, "records": [runs[r][3] for r in CONFIG["runs"]],
            "folds": folds, "predictions": predictions}


def summarize(results, output):
    rows = [f for result in results for f in result["folds"]]
    folds = pd.DataFrame(rows)
    folds.to_csv(output / "folds.csv", index=False)
    predictions = pd.DataFrame([p for result in results for p in result["predictions"]])
    predictions.to_csv(output / "predictions.csv", index=False)
    participants = folds.groupby("subject").balanced_accuracy.agg(["mean", "std"])
    participants.to_csv(output / "participants.csv")
    summary = {"participants": len(results), "folds": len(rows), "trials": len(predictions),
               "mean_participant_balanced_accuracy": float(participants["mean"].mean()),
               "sd_participant_balanced_accuracy": float(participants["mean"].std(ddof=1)),
               "chance_balanced_accuracy": 0.5,
               "data_bytes": sum(r["source_bytes"] for result in results for r in result["records"]),
               "inference": "Descriptive validation only; no significance or population claim."}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    fig, ax = plt.subplots(figsize=(6.4, 3.6), layout="constrained")
    offsets = np.linspace(-0.18, 0.18, len(CONFIG["runs"]))
    for offset, run in zip(offsets, CONFIG["runs"], strict=True):
        subset = folds[folds.held_out_run == run]
        ax.scatter(subset.subject + offset, subset.balanced_accuracy,
                   marker={4: "o", 8: "s", 12: "^"}[run], label=f"Held-out run {run}")
    ax.scatter(participants.index, participants["mean"], color="black", marker="_", s=160,
               label="Participant mean")
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="Chance reference")
    ax.set(xlabel="Participant", ylabel="Balanced accuracy (proportion)", ylim=(0, 1.03),
           xticks=CONFIG["subjects"], xticklabels=[f"S{s:03d}" for s in CONFIG["subjects"]])
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), frameon=False)
    for suffix in ["png", "svg"]:
        fig.savefig(output / f"held_out_runs.{suffix}", dpi=180, bbox_inches="tight")
    plt.close(fig)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    mne.set_log_level("ERROR")
    start = time.perf_counter()
    results = []
    for subject in CONFIG["subjects"]:
        path = args.output / f"S{subject:03d}.json"
        if path.exists():
            result = json.loads(path.read_text())
        else:
            result = evaluate_subject(args.data, subject)
            path.write_text(json.dumps(result, indent=2) + "\n")
        results.append(result)
        print(f"S{subject:03d}: {[round(f['balanced_accuracy'], 6) for f in result['folds']]}", flush=True)
    summary = summarize(results, args.output)
    environment = {p: importlib.metadata.version(p) for p in
                   ["mne", "numpy", "scipy", "scikit-learn", "matplotlib", "pandas"]}
    environment.update(python=platform.python_version(), platform=platform.platform(),
                       elapsed_seconds=time.perf_counter() - start)
    (args.output / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    (args.output / "config.json").write_text(json.dumps(CONFIG, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
