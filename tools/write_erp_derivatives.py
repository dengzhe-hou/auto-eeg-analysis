"""Write ERP results as a BIDS-Derivatives dataset; see templates/bids_derivatives."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re


def start_derivative(root, *, pipeline, source_doi, source_version, name=None):
    """Create the derivative root with its description and .bidsignore."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    doi = source_doi if source_doi.startswith("doi:") else "doi:" + source_doi
    (root / "dataset_description.json").write_text(json.dumps({
        "Name": name or pipeline, "BIDSVersion": "1.10.0", "DatasetType": "derivative",
        "GeneratedBy": [{"Name": pipeline}],
        "SourceDatasets": [{"DOI": doi, "Version": str(source_version)}]}, indent=2) + "\n", encoding="utf-8")
    (root / ".bidsignore").write_text("*_erp.tsv\n*_erp.json\n", encoding="utf-8")
    (root / "README").write_text(f"Derivatives of {doi} (version {source_version}) written by {pipeline}.\n", encoding="utf-8")
    return root


def write_subject_erp(root, *, subject, task, contrast, times_s, values_uv):
    """Write one subject's waveform as sub-XXX/eeg/sub-XXX_task-T_desc-C_erp.tsv plus sidecar."""
    for label, value in (("task", task), ("contrast", contrast)):
        if not re.fullmatch(r"[0-9a-zA-Z]+", value):
            raise ValueError(f"BIDS {label} label must be alphanumeric: {value!r}")
    if len(times_s) != len(values_uv):
        raise ValueError("times_s and values_uv differ in length")
    folder = Path(root) / subject / "eeg"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{subject}_task-{task}_desc-{contrast}_erp"
    with (folder / (stem + ".tsv")).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["time_s", "value_uv"])
        writer.writerows(zip(map(float, times_s), map(float, values_uv)))
    (folder / (stem + ".json")).write_text(json.dumps({
        "Description": f"{contrast} difference wave averaged over the planned ROI",
        "time_s": {"Units": "s"}, "value_uv": {"Units": "uV"}}, indent=2) + "\n", encoding="utf-8")
    return folder / (stem + ".tsv")
