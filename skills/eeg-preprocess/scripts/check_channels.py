"""Check actual MNE EEG picks against documented identities and the approved set.

Channel roles must come from recording documentation or a confirmed channel map,
not from the same reader's default EEG labels. No identity is inferred here.
"""
from __future__ import annotations

import mne


def check_eeg_channels(raw, *, expected_channels, channel_roles, mapping_source):
    """Return the checked, non-bad EEG set; raise before changing any samples.

    ``channel_roles`` maps labels to recording roles, with ``scalp_eeg`` for
    electrodes eligible for this analysis. Other values (e.g. ``eog``, ``ecg``,
    ``mastoid``, ``auxiliary``) are excluded. ``expected_channels`` is the
    approved analysis/reference set, after the planned handling of bad channels.
    """
    if not mapping_source.strip():
        raise ValueError("Provide the channel identity mapping source")
    indices = mne.pick_types(raw.info, meg=False, eeg=True, exclude="bads")
    actual = [raw.ch_names[i] for i in indices]
    if not actual:
        raise ValueError("No non-bad EEG channels selected")
    unknown = [name for name in actual if name not in channel_roles]
    if unknown:
        raise ValueError(f"Channel identities unresolved: {unknown}")
    non_scalp = [name for name in actual if channel_roles[name] != "scalp_eeg"]
    if non_scalp:
        raise ValueError(f"Non-scalp channels typed as EEG: {non_scalp}; correct types or picks first")
    expected = list(expected_channels)
    if len(expected) != len(set(expected)):
        raise ValueError("Approved channel set contains duplicates")
    if set(actual) != set(expected):
        raise ValueError(f"EEG set differs from the approved set: "
                         f"missing={sorted(set(expected) - set(actual))}, "
                         f"extra={sorted(set(actual) - set(expected))}")
    return {
        "mapping_source": mapping_source,
        "eeg_channels": actual,
        "excluded_channels": [name for name in raw.ch_names if name not in actual],
        "bad_channels": list(raw.info["bads"]),
    }


def apply_average_reference(raw, *, expected_channels, channel_roles, mapping_source,
                            projection):
    """Check the actual reference contributors, then modify ``raw`` in place.

    The caller must specify whether the approved operation applies the reference
    or adds a projector. A pending projector may change if channels/bads change;
    repeat the check immediately before applying it in that case.
    """
    record = check_eeg_channels(raw, expected_channels=expected_channels,
                                channel_roles=channel_roles, mapping_source=mapping_source)
    raw.set_eeg_reference("average", projection=projection, ch_type="eeg")
    record["operation"] = "add_average_reference_projector" if projection else "apply_average_reference"
    return record
