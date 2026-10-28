## Domain Knowledge

### Pernet et al. 2019: EEG-BIDS specification
- The EEG extension to BIDS (Brain Imaging Data Structure) standardizes how EEG data are organized.
- Key principle: all metadata that a researcher needs to analyze EEG data should be machine-readable in the BIDS sidecar files.
- `PowerLineFrequency` is REQUIRED (50 Hz in Europe/Asia, 60 Hz in Americas).
- `EEGReference` is REQUIRED — the online reference electrode during acquisition.
- Event files (`_events.tsv`) must use onset in seconds (not samples) relative to recording start.
- Cite: Pernet, C. R., et al. (2019). EEG-BIDS, an extension to the brain imaging data structure for electroencephalography. Scientific Data, 6, 103.

### BIDS-Derivatives chain (Pernet et al. 2019; MNE-BIDS-Pipeline)
- Raw-to-BIDS conversion is only the first link. The BIDS spec defines a
  `derivatives/` convention so that every processed product carries its own
  provenance, and EEG-BIDS adopts it. Emit a **derivatives chain**, not a
  one-shot conversion.
- Each downstream AEA stage (`eeg-preprocess`, `eeg-ica`, `eeg-epoch`, ...) should
  write into its own derivative subtree, e.g.
  `bids-stage/derivatives/<stage>/`, with a **per-derivative
  `dataset_description.json`** that records:
  - `"DatasetType": "derivative"`,
  - `"GeneratedBy": [{"Name": "<stage>", "Version": "<version>"}]` — the actual
    pipeline step and version that produced this subtree (not just the root
    `auto-eeg-analysis` entry),
  - `"SourceDatasets": [...]` — pointing at the dataset (raw or upstream
    derivative) it consumed.
  ```python
  deriv_root = bids_root / 'derivatives' / stage_name
  deriv_desc = {
      "Name": f"{dataset_name} — {stage_name}",
      "BIDSVersion": BIDS_VERSION,
      "DatasetType": "derivative",
      "GeneratedBy": [{"Name": stage_name, "Version": stage_version}],
      "SourceDatasets": [{"URL": "../.." }],   # raw root or upstream derivative
  }
  ```
- Payoff: provenance is machine-traceable from any derivative back to raw, the
  whole run is re-ingestible by standard BIDS apps, and the flat
  `REPRO_RECEIPT` is brought into line with the standard derivatives spec —
  this is the layout MNE-BIDS-Pipeline already produces.
- Cite: Pernet, C. R., et al. (2019). EEG-BIDS, an extension to the brain imaging data structure for electroencephalography. Scientific Data, 6, 103 (Derivatives extension); MNE-BIDS-Pipeline (mne.tools/mne-bids-pipeline).

### Appelhoff et al. 2019: MNE-BIDS
- MNE-BIDS automates BIDS conversion from MNE-Python Raw objects.
- `write_raw_bids()` handles format conversion, sidecar generation, and event extraction.
- `BIDSPath` is the central object for constructing BIDS-compliant file paths.
- `read_raw_bids()` reads BIDS-formatted data back with all metadata attached.
- `print_dir_tree()` visualizes the BIDS directory for quick verification.
- Supports all major EEG formats via MNE-Python readers.
- Cite: Appelhoff, S., et al. (2019). MNE-BIDS: Organizing electrophysiological data into the BIDS format and facilitating their analysis. Journal of Open Source Software, 4(44), 1896.

### Gorgolewski et al. 2016: BIDS for neuroimaging
- BIDS was originally designed for MRI data and later extended to EEG, MEG, iEEG.
- Core principles: human-readable directory names, machine-readable JSON sidecars, TSV for tabular data.
- File naming convention: `sub-<label>[_ses-<label>]_task-<label>[_run-<index>]_<suffix>.<extension>`.
- `dataset_description.json` is the only REQUIRED file at the dataset root.
- `participants.tsv` is RECOMMENDED for subject-level demographics.
- Cite: Gorgolewski, K. J., et al. (2016). The brain imaging data structure, a format for organizing and describing outputs of neuroimaging experiments. Scientific Data, 3, 160044.
