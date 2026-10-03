"""Auto-Brief: read EEG file headers and generate a draft DATASET_BRIEF.md.

Usage:
    python tools/auto_brief.py --raw-dir projects/my-study/raw/ \
        --out projects/my-study/DATASET_BRIEF.md

The script scans all EEG files in raw-dir, extracts metadata from headers,
and writes a draft DATASET_BRIEF.md with auto-filled fields marked [AUTO]
and user-required fields marked [USER].

Supports: .bdf, .edf, .set, .fif, .vhdr
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _require_mne():
    try:
        import mne
        return mne
    except ImportError:
        sys.stderr.write(
            "ERROR: mne not installed. Install with `pip install mne[hdf5]` "
            "or activate the AEA environment.\n"
        )
        raise SystemExit(2)


def _load_raw_lazy(path: Path):
    """Load raw with preload=False (header only, fast)."""
    mne = _require_mne()
    suffix = path.suffix.lower()
    loaders = {
        ".bdf": mne.io.read_raw_bdf,
        ".edf": mne.io.read_raw_edf,
        ".set": mne.io.read_raw_eeglab,
        ".fif": mne.io.read_raw_fif,
        ".vhdr": mne.io.read_raw_brainvision,
    }
    loader = loaders.get(suffix)
    if not loader:
        return None
    try:
        return loader(path, preload=False, verbose="ERROR")
    except Exception as e:
        sys.stderr.write(f"WARN: could not read {path}: {e}\n")
        return None


def _find_eeg_files(raw_dir: Path) -> list[Path]:
    """Find all supported EEG files in directory."""
    exts = {".bdf", ".edf", ".set", ".fif", ".vhdr"}
    files = []
    for f in sorted(raw_dir.iterdir()):
        if f.suffix.lower() in exts and not f.name.startswith("."):
            files.append(f)
    return files


def _infer_system(raw) -> str:
    """Try to guess acquisition system from file metadata."""
    info = raw.info
    desc = info.get("description", "") or ""
    meas_id = info.get("meas_id") or {}

    # BioSemi BDF files
    if hasattr(raw, "filenames") and raw.filenames:
        fname = str(raw.filenames[0])
        if fname.endswith(".bdf"):
            return "BioSemi (inferred from .bdf format)"
        if fname.endswith(".vhdr"):
            return "Brain Products (inferred from .vhdr format)"
        if fname.endswith(".edf"):
            return "Unknown (EDF format — check device documentation)"
        if fname.endswith(".fif"):
            return "Unknown (.fif format — check acquisition documentation)"

    return "Unknown (check acquisition documentation)"


def _extract_events(raw) -> dict[str, Any]:
    """Extract event/marker information from raw data."""
    mne = _require_mne()
    try:
        events = mne.find_events(raw, shortest_event=1, verbose="ERROR")
        if len(events) == 0:
            # Try annotations
            events, event_id = mne.events_from_annotations(raw, verbose="ERROR")
            if len(events) > 0:
                code_counts = Counter(events[:, 2])
                return {
                    "source": "annotations",
                    "event_id": {str(k): int(v) for k, v in event_id.items()},
                    "code_counts": {str(k): int(v) for k, v in code_counts.items()},
                    "total": int(len(events)),
                }
        if len(events) > 0:
            code_counts = Counter(events[:, 2])
            return {
                "source": "stim_channel",
                "code_counts": {str(k): int(v) for k, v in code_counts.items()},
                "total": int(len(events)),
            }
    except Exception:
        pass

    return {"source": "none_found", "code_counts": {}, "total": 0}


def scan_raw_dir(raw_dir: Path) -> dict[str, Any]:
    """Scan all EEG files and extract metadata."""
    files = _find_eeg_files(raw_dir)
    if not files:
        return {"error": f"No EEG files found in {raw_dir}"}

    results = {
        "n_files": len(files),
        "format": files[0].suffix.lower(),
        "files": [],
    }

    # Read first file in detail
    first_raw = _load_raw_lazy(files[0])
    if first_raw is None:
        return {"error": f"Could not read {files[0]}"}

    info = first_raw.info

    mne = _require_mne()

    # Channel info
    ch_names = info["ch_names"]
    ch_types = [mne.channel_type(info, i) for i in range(len(ch_names))]
    type_counts = dict(Counter(ch_types))

    eeg_channels = [ch for ch, t in zip(ch_names, ch_types) if t == "eeg"]
    eog_channels = [ch for ch, t in zip(ch_names, ch_types) if t == "eog"]
    misc_channels = [ch for ch, t in zip(ch_names, ch_types) if t not in ("eeg", "eog", "stim")]

    mne = _require_mne()

    results["first_file"] = {
        "path": str(files[0]),
        "sfreq": float(info["sfreq"]),
        "duration_s": float(first_raw.times[-1]),
        "n_channels_total": int(info["nchan"]),
        "n_eeg_channels": len(eeg_channels),
        "eeg_channel_names": eeg_channels,
        "eog_channels": eog_channels,
        "misc_channels": misc_channels,
        "channel_type_counts": type_counts,
        "system_guess": _infer_system(first_raw),
        "highpass": float(info["highpass"]),
        "lowpass": float(info["lowpass"]),
    }

    # Events from first file (needs preload for stim channel)
    try:
        first_raw_loaded = _load_raw_lazy(files[0])
        if first_raw_loaded is not None:
            # Need to preload for event extraction
            first_raw_loaded.load_data()
            results["first_file"]["events"] = _extract_events(first_raw_loaded)
            del first_raw_loaded
    except Exception as e:
        results["first_file"]["events"] = {"error": str(e)}

    # Quick scan of remaining files (header only)
    for f in files[1:]:
        raw = _load_raw_lazy(f)
        if raw is not None:
            results["files"].append({
                "path": str(f),
                "sfreq": float(raw.info["sfreq"]),
                "n_channels": int(raw.info["nchan"]),
            })

    results["n_subjects"] = len(files)
    results["consistent_sfreq"] = all(
        f.get("sfreq") == results["first_file"]["sfreq"]
        for f in results["files"]
    )
    results["consistent_channels"] = all(
        f.get("n_channels") == results["first_file"]["n_channels_total"]
        for f in results["files"]
    )

    return results


def generate_brief(scan: dict[str, Any], raw_dir: Path) -> str:
    """Generate a draft DATASET_BRIEF.md from scan results."""
    f = scan["first_file"]
    events = f.get("events", {})

    # Format event table
    event_rows = ""
    if events.get("code_counts"):
        for code, count in sorted(events["code_counts"].items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
            avg_per_subj = count  # from first subject
            event_rows += f"| `[USER: condition name]` | `{code}` | `~{avg_per_subj}` | [USER] |\n"
    else:
        event_rows = "| `[USER]` | `[USER]` | `[USER]` | No events auto-detected |\n"

    # Format channel list (abbreviated if >32)
    eeg_ch = f["eeg_channel_names"]
    if len(eeg_ch) > 32:
        ch_display = ", ".join(eeg_ch[:16]) + f", ... ({len(eeg_ch)} total)"
    else:
        ch_display = ", ".join(eeg_ch)

    # Infer online filter from header
    online_filter = ""
    if f["highpass"] > 0 or f["lowpass"] < f["sfreq"] / 2:
        parts = []
        if f["highpass"] > 0:
            parts.append(f"{f['highpass']} Hz HP")
        if f["lowpass"] < f["sfreq"] / 2:
            parts.append(f"{f['lowpass']} Hz LP")
        online_filter = " + ".join(parts) + " (from file header)"
    else:
        online_filter = "[USER: check acquisition documentation]"

    brief = f"""# DATASET_BRIEF — `[USER: study short name]`

> Auto-generated by `tools/auto_brief.py` from `{raw_dir}/`.
> Fields marked **[AUTO]** were extracted from EEG file headers.
> Fields marked **[USER]** require your input — the agent will ask about these.

## 1. Study identity

- **Study short name:** `[USER: e.g., face-erp-2026]`
- **Paradigm:** `[USER: e.g., N170 face inversion; oddball; resting-state]`
- **Hypothesis (one sentence):** `[USER]`
- **Linked publication / preprint (if any):** `[USER: DOI or arXiv ID, or "none"]`

## 2. Subjects

- **N enrolled / analyzed:** `{scan['n_subjects']} files detected` **[AUTO]** — `[USER: confirm N analyzed, note exclusions]`
- **Group structure:** `[USER: single-group | between-group | within-subject]`
- **Demographics range:** `[USER: age range, handedness, sex/gender]`
- **Exclusion criteria (a priori):** `[USER: e.g., >30% epochs rejected]`

## 3. Acquisition

- **System:** `{f['system_guess']}` **[AUTO]** — `[USER: confirm exact model]`
- **Channels:** `{f['n_eeg_channels']} EEG ({ch_display})` **[AUTO]**{f' + {len(f["eog_channels"])} EOG ({", ".join(f["eog_channels"])})' if f["eog_channels"] else ''}
- **Sampling rate (raw):** `{f['sfreq']} Hz` **[AUTO]**
- **Online filter:** `{online_filter}`
- **Online reference:** `[USER: e.g., CMS/DRL (BioSemi), FCz, linked mastoid]`
- **Channel locations:** `[USER: standard-1020 | individual digitization]`
- **Marker / trigger source:** `[USER: parallel port | LSL | photodiode]`

## 4. Conditions and trials

| Condition | Marker code | N trials / subject | Notes |
|---|---|---|---|
{event_rows}
- **Block structure:** `[USER]`
- **ITI:** `[USER]`
- **Trial timing:** `[USER]`

## 5. Preprocessing decisions (a priori, NOT after seeing data)

- **Bandpass for analysis:** `[USER: e.g., 0.1–40 Hz zero-phase FIR]` (default: 0.1–40 Hz)
- **Notch:** `[USER: 50 Hz | 60 Hz | none]`
- **Re-reference scheme:** `[USER: average | linked-mastoid | REST]` (default: average)
- **Bad channel detection rule:** `RANSAC + manual review` (default)
- **Epoch window:** `[USER: e.g., −0.2 to 0.6 s relative to stimulus]`
- **Baseline:** `[USER: e.g., −0.2 to 0 s]`
- **Artifact rejection:** `AutoReject (local)` (default)

## 6. Analyses planned

Tick the ones planned:

- [ ] ERP — see `ANALYSIS_PLAN.md` for contrasts
- [ ] Time-frequency (TFR) — bands: `[USER]`
- [ ] Connectivity — metric: `[USER]` ROI: `[USER]`
- [ ] Microstate — k = `[USER]`
- [ ] Source localization — head model: `[USER]`

## 7. Statistical plan

- **Primary test:** `cluster permutation, channel × time` (default)
- **Permutations:** `5000` (default)
- **Cluster-forming threshold:** `t-threshold from p<0.05` (default)
- **Multiple-comparisons strategy:** `[USER: Bonferroni | hierarchical | none]`
- **Effect-size reporting:** `Cohen's d` (default)

## 8. Backends preferred

- Preprocessing: `mne` (default)
- ICA: `mne (mne-icalabel)` (default)
- Cluster permutation: `mne` (default)
- Microstate: `pycrostates` (default)
- Source: `mne+FreeSurfer` (default)

## 9. Data location and provenance

- **Raw path:** `{raw_dir.resolve()}` **[AUTO]**
- **Format:** `{scan['format']}` **[AUTO]**
- **License / consent scope:** `[USER: can data leave the lab machine?]`
- **Backup location:** `[USER]`

---

> **Data consistency check [AUTO]:**
> - Sampling rate consistent across files: {'Yes' if scan.get('consistent_sfreq', True) else 'NO — check files!'}
> - Channel count consistent across files: {'Yes' if scan.get('consistent_channels', True) else 'NO — check files!'}
> - Total events in first file: {events.get('total', 'unknown')}
> - Event source: {events.get('source', 'unknown')}

> **For the agent:** fields marked [USER] still need input. Ask the user about them conversationally — do not dump the entire template. Prioritize: paradigm, condition→marker mapping, epoch window, hypothesis. Other fields have sensible defaults.
"""
    return brief


def main():
    p = argparse.ArgumentParser(description="Auto-generate DATASET_BRIEF.md from EEG file headers")
    p.add_argument("--raw-dir", required=True, help="Path to raw/ directory with EEG files")
    p.add_argument("--out", required=True, help="Output path for DATASET_BRIEF.md")
    p.add_argument("--json", help="Also write raw scan results as JSON")
    args = p.parse_args()

    raw_dir = Path(args.raw_dir)
    if not raw_dir.is_dir():
        sys.stderr.write(f"ERROR: {raw_dir} is not a directory\n")
        raise SystemExit(1)

    print(f"Scanning {raw_dir} ...")
    scan = scan_raw_dir(raw_dir)

    if "error" in scan:
        sys.stderr.write(f"ERROR: {scan['error']}\n")
        raise SystemExit(1)

    # Write JSON if requested
    if args.json:
        Path(args.json).write_text(json.dumps(scan, indent=2, default=str), encoding="utf-8")
        print(f"Scan results: {args.json}")

    # Generate and write brief
    brief = generate_brief(scan, raw_dir)
    Path(args.out).write_text(brief, encoding="utf-8")
    print(f"Draft DATASET_BRIEF.md: {args.out}")

    # Print summary
    f = scan["first_file"]
    print(f"\nSummary:")
    print(f"  Files: {scan['n_files']}")
    print(f"  Format: {scan['format']}")
    print(f"  Channels: {f['n_eeg_channels']} EEG")
    print(f"  Sampling rate: {f['sfreq']} Hz")
    print(f"  Duration: {f['duration_s']:.1f} s")
    events = f.get("events", {})
    if events.get("code_counts"):
        print(f"  Event codes: {events['code_counts']}")
    print(f"\n  [USER] fields remaining — agent will ask conversationally.")


if __name__ == "__main__":
    main()
