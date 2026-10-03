
import os
import pandas as pd
from mne import io, filtering, resample, set_eeg_reference
from mne.io import read_raw_eeglab
from mne.events import make_fixed_length_events
from mne.preprocessing import combine_evoked
from mne.epochs import read_epochs
from mne.datasets import sample
import numpy as np

mne.set_log_level("ERROR")

output_dir = "/tmp/claude-1137/-home-hou-Research-auto-eeg-analysis/b4a153ed-22fa-4b6a-ad04-d134656fecf4/scratchpad/gen_scale/C_llama8b"
os.makedirs(output_dir, exist_ok=True)

result_json_path = os.path.join(output_dir, 'result.json')

excluded_subjects = []

for sub in range(1, 41):
    subject_id = f"sub-{str(sub).zfill(3)}"

    # load raw eeg data
    raw = read_raw_eeglab(f"/home/hou/mne_data/MNE-erpcoremmn2021-data/{subject_id}/eeg/{subject_id}_task-MMN_eeg.set", preload=True)

    # drop unwanted channels
    raw.drop_channels(["HEOG_left","HEOG_right","VEOG_lower"])

    # set montage and filter data
    raw.set_montage("standard_1020", match_case=False, on_missing="warn")
    raw.filter(0.1, 30.0)
    raw.resample(256.0)

    # reference to average
    raw.set_eeg_reference("average", projection=False)

    # load events and create epochs
    events = pd.read_csv(f"/home/hou/mne_data/MNE-erpcoremmn2021-data/{subject_id}/eeg/{subject_id}_task-MMN_events.tsv", sep="\t")
    events = events[(events['value'] == 80) | (events['value'] == 70)]
    sample = round(events['onset']*256)
    events['sample'] = sample
    events = make_fixed_length_events(events, event_id={"standard":80,"deviant":70}, tmin=-0.2, tmax=0.5)

    epochs = read_epochs(raw, events, event_id={"standard":80,"deviant":70}, tmin=-0.2, tmax=0.5, baseline=(-0.2,0.0), preload=True, reject=dict(eeg=100e-6))

    if len(epochs["deviant"]) < 50 or len(epochs["standard"]) < 150:
        excluded_subjects.append(subject_id)
        continue

    # compute grand average for deviants and standards
    diff = combine_evoked([epochs["deviant"].average(), epochs["standard"].average()], weights=[1,-1])

    # extract relevant channels and time points
    value = np.mean(diff.data[Fz,FCz,Cz,0:128], axis=0)
    value = np.mean(value[np.where(0.100<=diff.times<=0.250)*256])
    value *= 1e6

    result_json_data = {
        "per_subject": {subject_id: round(value,3)},
        "excluded": excluded_subjects,
        "n_analyzed": len(result_json_data["per_subject"]),
        "grand_mean_uV": value
    }
    
    with open(result_json_path, 'w') as f:
        import json
        json.dump(result_json_data, f)


