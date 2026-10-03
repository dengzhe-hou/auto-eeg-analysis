import os
import json
import pandas as pd
import numpy as np
import mne

mne.set_log_level("ERROR")
output_dir = "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/C_qwen32b"
os.makedirs(output_dir, exist_ok=True)
result_file = os.path.join(output_dir, "result.json")

subjects = [f"sub-{i:03d}" for i in range(1, 41)]
per_subject = {}
excluded = []
grand_mean_uV = []

for sub in subjects:
    try:
        raw_path = f"/home/hou/mne_data/MNE-erpcoremmn2021-data/{sub}/eeg/{sub}_task-MMN_eeg.set"
        events_tsv = f"/home/hou/mne_data/MNE-erpcoremmn2021-data/{sub}/eeg/{sub}_task-MMN_events.tsv"

        raw = mne.io.read_raw_eeglab(raw_path, preload=True)
        raw.drop_channels(["HEOG_left", "HEOG_right", "VEOG_lower"])
        raw.set_montage("standard_1020", match_case=False, on_missing="warn")
        raw.filter(0.1, 30.0)
        raw.resample(256.0)
        raw.set_eeg_reference("average", projection=False)

        events_df = pd.read_csv(events_tsv, sep="\t")
        events_df = events_df[events_df["value"].isin([70, 80])]
        events_df["sample"] = round(events_df["onset"] * 256).astype(int)
        events = events_df[["sample", "duration", "value"]].values

        epochs = mne.Epochs(raw, events, event_id={"standard": 80, "deviant": 70}, tmin=-0.2, tmax=0.5,
                            baseline=(-0.2, 0.0), preload=True, reject=dict(eeg=100e-6))

        if len(epochs["deviant"]) < 50 or len(epochs["standard"]) < 150:
            excluded.append(sub)
            continue

        diff = mne.combine_evoked([epochs["deviant"].average(), epochs["standard"].average()], weights=[1, -1])
        channels_of_interest = ["Fz", "FCz", "Cz"]
        times_of_interest = np.where((diff.times >= 0.1) & (diff.times <= 0.25))[0]

        value = diff.data[np.isin(diff.ch_names, channels_of_interest), :][:, times_of_interest].mean() * 1e6
        per_subject[sub] = round(value, 3)
        grand_mean_uV.append(value)

    except Exception as e:
        excluded.append(sub)

grand_mean_uV = np.mean(grand_mean_uV) if grand_mean_uV else np.nan

result_data = {
    "per_subject": per_subject,
    "excluded": excluded,
    "n_analyzed": len(per_subject),
    "grand_mean_uV": round(grand_mean_uV, 3) if not np.isnan(grand_mean_uV) else None,
    "choices": {"method": "mean", "channels": ["Fz", "FCz", "Cz"], "times": [0.100, 0.250]}
}

with open(result_file, 'w') as f:
    json.dump(result_data, f)

