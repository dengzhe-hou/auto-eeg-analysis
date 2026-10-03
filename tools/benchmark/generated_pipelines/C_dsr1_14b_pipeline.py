import mne
from os import path, makedirs
from pandas import read_csv
import numpy as np

mne.set_log_level("ERROR")

subjects = [f"sub-0{i:03d}" for i in range(1, 41)]
results_dir = "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/C_dsr1_14b"
makedirs(results_dir, exist_ok=True)

per_subject = {}
excluded = []
n_analyzed = 0
grand_mean_uV = 0.0

for sub in subjects:
    try:
        # Read data
        raw = mne.io.read_raw_eeglab(f"/home/hou/mne_data/MNE-erpcoremmn2021-data/{sub}/eeg/{sub}_task-MMN_eeg.set", preload=True)
        
        # Drop channels and set montage
        raw.drop_channels(["HEOG_left","HEOG_right","VEOG_lower"])
        raw.set_montage("standard_1020", match_case=False, on_missing="warn")
        
        # Filter and resample
        raw.filter(0.1, 30.0)
        raw.resample(256.0)
        
        # Set reference
        raw.set_eeg_reference("average", projection=False)
        
        # Read events
        events = read_csv(f"/home/hou/mne_data/MNE-erpcoremmn2021-data/{sub}/eeg/{sub}_task-MMN_events.tsv", sep="\t")
        events = events[events.value.isin([80, 70])]
        events.onset = events.onset.round() * 256
        
        # Create epochs
        epochs = mne.Epochs(raw, events, event_id={"standard":80,"deviant":70}, 
                           tmin=-0.2, tmax=0.5, baseline=(-0.2,0.0), preload=True,
                           reject=dict(eeg=100e-6))
        
        # Check trial counts
        if len(epochs["deviant"]) < 50 or len(epochs["standard"]) < 150:
            excluded.append(sub)
            continue
        
        # Compute difference and extract statistics
        diff = mne.combine_evoked([epochs["deviant"].average(), epochs["standard"].average()], weights=[1,-1])
        
        # Extract data for specified channels and time window
        ch_names = ['Fz', 'FCz', 'Cz']
        ch_indices = [diff.ch_names.index(ch) for ch in ch_names]
        times_range = (0.100, 0.250)
        
        data = diff.data[ch_indices, :]
        time_mask = np.where((diff.times >= times_range[0]) & (diff.times <= times_range[1]))[0]
        if len(time_mask) == 0:
            excluded.append(sub)
            continue
        
        # Mean across channels and valid time points
        mean_val = data[:, time_mask].mean() * 1e6
        
        per_subject[sub] = round(mean_val, 3)
        
        n_analyzed +=1
        grand_mean_uV += mean_val
        
    except Exception as e:
        excluded.append(sub)

# Calculate final values
grand_mean_uV = grand_mean_uV / n_analyzed if n_analyzed >0 else 0.0

# Prepare results dictionary
results = {
    "per_subject": per_subject,
    "excluded": excluded,
    "n_analyzed": n_analyzed,
    "grand_mean_uV": grand_mean_uV,
    "choices": {
        "rounding": 3,
        "channels": ['Fz', 'FCz', 'Cz'],
        "time_window": (0.100, 0.250)
    }
}

# Save to JSON
with open(path.join(results_dir, "result.json"), "w") as f:
    import json
    json.dump(results, f, indent=4)
