# Channel identity and actual analysis picks

Use this check before average reference, channel ranking or channel-averaged
features when imports may label auxiliary signals as EEG. It implements the
existing requirement to exclude non-scalp signals; it does not choose a new
reference scheme or determine physiological identity from a label alone.

## Establish the mapping

Read the recording's channel table, acquisition documentation or confirmed study
brief. Record each relevant label's role and the source of that assignment.
Distinguish a scalp derivation recorded against a mastoid from a standalone
mastoid channel. Do not remove a scalp derivation merely because its name
contains a reference suffix.

MNE's EDF reader defaults to `infer_types=False`, and unknown prefixes can still
be assigned EEG with inference enabled. Thus `raw.get_channel_types()` reports
the software's classification, not independent evidence about the sensor.
Correct known EOG/ECG/EMG/misc types with `raw.set_channel_types(...)`, using
the dataset mapping. Leave unresolved identities recorded as unresolved instead
of guessing from a regex or treating every imported channel as scalp EEG.

## Check immediately before the operation

The approved plan supplies the channels, handling of bad/interpolated channels,
and reference order. After those operations, compare the actual non-bad MNE EEG
picks with that approved set. A mismatch must be resolved before applying the
reference or computing an EEG-only feature.

For an approved average reference, use the bundled helper rather than generating
another unchecked `set_eeg_reference('average')` call. This example expects
`AEA_ROOT`, `raw`, `approved_reference_channels`, `documented_channel_roles`,
`channel_mapping_source` and `planned_projection` from the current study:

```python
import runpy

channel_checks = runpy.run_path(str(
    AEA_ROOT / 'skills/eeg-preprocess/scripts/check_channels.py'))
reference_check = channel_checks['apply_average_reference'](
    raw,
    expected_channels=approved_reference_channels,
    channel_roles=documented_channel_roles,
    mapping_source=channel_mapping_source,
    projection=planned_projection,
)
# Include reference_check in this subject's preprocess_summary.json.
```

For channel ranking or channel-averaged features, call `check_eeg_channels` with
the same named arguments (except `projection`) on the data object that will be
used in the computation, then use its `eeg_channels` as the picks. This catches
auxiliary signals left in the actual EEG set; checking a separate cleaned copy
does not validate an operation on the original data.

The checker fails on unknown selected identities, a non-scalp role still typed
EEG, or a difference from the approved set. It does not automatically drop
channels, select another reference or invent a mapping. If using a pending
projector, preserve that state in the summary; changes to picks/bads require a
new check before application. This helper checks the contributor set, not rank,
the correctness of the supplied mapping or whether the scientific reference
choice is suitable for this montage.

## Sources

- [MNE EDF reader](https://mne.tools/stable/generated/mne.io.read_raw_edf.html):
  `eog`, `misc`, `infer_types` and unknown-prefix behavior.
- [MNE reference tutorial](https://mne.tools/stable/auto_tutorials/preprocessing/55_setting_eeg_reference.html):
  average reference, exclusion of bad channels, and pending projectors.
- [MNE channel type API](https://mne.tools/stable/generated/mne.io.Raw.html#mne.io.Raw.set_channel_types):
  explicitly assigning software channel types.

Checked against the documentation on 2026-10-28. The dataset mapping remains a
study input, not a bundled benchmark answer.
