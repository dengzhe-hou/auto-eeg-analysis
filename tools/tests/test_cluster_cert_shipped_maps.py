"""The four committed shipped cluster-map pairs (MNE vs FieldTrip) must stay in conformance.

The paper states that the observed t-maps agree within 1e-12 relative and that the cluster
partitions are identical (Table 4). Until now CI checked the JSON summaries of that comparison,
not the committed maps themselves; this test recomputes both criteria from the .mat dumps.
"""
from pathlib import Path

import numpy as np
import pytest
import scipy.io

DUMPS = Path(__file__).resolve().parents[1] / "benchmark" / "cluster_cert" / "dumps_shipped"
COMPONENTS = ["ERN", "N170", "N400", "P3"]
RTOL = 1e-12


KEYS = {"mne": ("tmap", "labelmap"), "ft": ("statmap", "labelmat")}   # MNE dumps are (times, channels); FieldTrip (channels, times)


def _load(prefix, component):
    d = scipy.io.loadmat(DUMPS / f"{prefix}_{component}.mat"); tk, lk = KEYS[prefix]
    t = np.asarray(d[tk], dtype=float); lab = np.rint(np.asarray(d[lk], dtype=float)).astype(int)
    return (t, lab) if prefix == "mne" else (t.T, lab.T)


def _same_partition(a, b):
    """Two integer label maps describe the same partition iff labels correspond one-to-one
    (background 0 must map to background 0)."""
    if a.shape != b.shape:
        return False
    fwd, bwd = {}, {}
    for x, y in zip(a.ravel().tolist(), b.ravel().tolist()):
        if (x == 0) != (y == 0):
            return False
        if fwd.setdefault(x, y) != y or bwd.setdefault(y, x) != x:
            return False
    return True


@pytest.mark.parametrize("component", COMPONENTS)
def test_shipped_maps_conform(component):
    t_mne, lab_mne = _load("mne", component)
    t_ft, lab_ft = _load("ft", component)
    assert t_mne.shape == t_ft.shape, f"{component}: shapes differ {t_mne.shape} vs {t_ft.shape}"
    scale = np.max(np.abs(t_mne))
    max_abs = float(np.max(np.abs(t_mne - t_ft)))
    assert max_abs <= RTOL * scale, f"{component}: t-map max|diff| {max_abs:.3e} exceeds {RTOL:g} x {scale:.3g}"
    assert _same_partition(lab_mne, lab_ft), f"{component}: cluster partitions differ"
    assert lab_mne.max() >= 1, f"{component}: no cluster in the shipped map"


def test_partition_check_rejects_a_merged_cluster():
    a = np.array([[1, 1, 0, 2, 2]]); b = np.array([[1, 1, 0, 1, 1]])
    assert not _same_partition(a, b)
    assert _same_partition(a, np.array([[7, 7, 0, 3, 3]]))
