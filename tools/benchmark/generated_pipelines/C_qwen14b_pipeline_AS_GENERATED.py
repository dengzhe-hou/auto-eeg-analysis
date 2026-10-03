import os
import numpy as np
import pandas as pd
import mne
from scipy.io import loadmat

mne.set_log_level("ERROR")

output_dir = "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/C_qwen14b"
os.makedirs(output_dir, exist_ok=True)

result_json_path = os.path.join(output_dir, "result.json")
excluded_subjects = []
n_analyzed = 0
grand_mean_uV = []

for sub in range(1, 41):
    subject_id = f"sub-{str(sub).zfill(3)}"
    
    raw_path = f"/home/hou/mne_data/MNE-erpcoremmn2021-data/{subject_id}/eeg/{subject_id}_task-MMN_eeg.set"
    
    if not os.path.exists(raw_path):
        excluded_subjects.append(subject_id)
        continue
    
    try:
        raw = mne.io.read_raw_eeglab(raw_path, preload=True)
        
        # Drop channels
        raw.drop_channels(["HEOG_left", "HEOG_right", "VEOG_lower"])
        
        # Set montage
        raw.set_montage("standard_1020", match_case=False, on_missing="warn")
        
        # Filter and resample
        raw.filter(0.1, 30.0)
        raw.resample(256.0)
        
        # Apply average reference
        raw.set_eeg_reference("average", projection=False)

        # Load events
        events_path = f"/home/hou/mne_data/MNE-erpcoremmn2021-data/{subject_id}/eeg/{subject_id}_task-MMN_events.tsv"
        events_df = pd.read_csv(events_path, sep="\t")
        
        # Keep only standard (80) and deviant (70)
        filtered_events = events_df[events_df['value'].isin([80, 70])]
        
        if len(filtered_events) == 0:
            excluded_subjects.append(subject_id)
            continue
        
        onset = filtered_events["onset"].values
        sample = np.round(onset * 256).astype(int)

        events = list(zip(sample, [1] * len(sample), [80 if x == 80 else 70 for x in filtered_events['value']]))

        epochs = mne.Epochs(raw, events=events, event_id={"standard": 80, "deviant": 70}, tmin=-0.2, tmax=0.5,
                            baseline=(-0.2, 0), preload=True, reject=dict(eeg=100e-6))

        if len(epochs["deviant"]) < 50 or len(epochs["standard"]) < 150:
            excluded_subjects.append(subject_id)
            continue

        deviant_avg = epochs["deviant"].average()
        standard_avg = epochs["standard"].average()

        diff_evoked = mne.combine_evoked([deviant_avg, standard_avg], weights=[1, -1])

        # Calculate mean over channels Fz, FCz, Cz and times 0.100 <= t <= 0.250
        chan_mask = [ch == "Fz" or ch == "FCz" or ch == "Cz" for ch in diff_evoked.ch_names]
        time_mask = (diff_evoked.times >= 0.1) & (diff_evoked.times <= 0.25)
        
        mean_value = np.mean(diff_evoked.data[chan_mask][:, time_mask], axis=(0, 1)) * 1e6

        n_analyzed += 1
        grand_mean_uV.append(mean_value)

    except Exception as e:
        print(f"Error processing {subject_id}: {str(e)}")
        excluded_subjects.append(subject_id)
    
mean_of_means = np.mean(grand_mean_uV, axis=0)[0]

result_dict = {
    "per_subject": {f"{sub}": round(value[0], 3) for sub, value in zip(range(1,41), grand_mean_uV)},
    "excluded": excluded_subjects,
    "n_analyzed": n_analyzed,
    "grand_mean_uV": mean_of_means.item(),
    "choices": {"made_by": "claude-1137", "model": "qwen-14b"}
}

import json
with open(result_json_path, 'w') as f:
    json.dump(result_dict, f)

