"""The figure must show the numbers it claims.

`eeg-figure` prescribes a written sanity checklist, but until now the only machine-verified
assertion about any figure in this repository was `assert fig is not None`. A plot that draws the
wrong channel, an axis in seconds under a caption saying milliseconds, or an SD band captioned as
SEM is wrong in a way no numeric test can see — and it is the artefact a reader actually believes.

These tests do two things, and the second matters as much as the first:

  1. the checks pass on a correct figure  — a check that rejects correct input gets switched off,
     and then it guards nothing. Both of these checks did exactly that on their first version.
  2. the checks catch a deliberately corrupted figure — otherwise they are decoration.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "benchmark"))
from figure_fidelity import (  # noqa: E402
    FigureFidelityError, check_axis_units, check_errorband_is, check_line, check_mask_matches,
)

N_SUB = 20


@pytest.fixture
def data():
    t = np.linspace(-0.2, 0.8, 257)
    truth = np.sin(2 * np.pi * 3 * t) * 2.0
    subj = truth[None, :] + np.random.default_rng(0).normal(0, 1.0, (N_SUB, t.size))
    return t, truth, subj, subj.std(0, ddof=1), (t > 0.30) & (t < 0.50)


@pytest.fixture
def good_fig(data):
    t, truth, _, sd, sig = data
    fig, ax = plt.subplots()
    ax.plot(t * 1000, truth, label="difference")
    ax.fill_between(t * 1000, truth - sd / np.sqrt(N_SUB), truth + sd / np.sqrt(N_SUB))
    ax.axvspan(t[sig].min() * 1000, t[sig].max() * 1000, alpha=0.2)
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("amplitude (µV)")
    yield ax
    plt.close(fig)


# --- 1. the checks must accept a correct figure -------------------------------------------------

def test_accepts_correct_line(good_fig, data):
    _, truth, *_ = data
    assert check_line(good_fig, truth) is not None


def test_accepts_correct_sem_band(good_fig, data):
    _, truth, _, sd, _ = data
    assert check_errorband_is(good_fig, truth, sd, kind="sem", n=N_SUB) is not None


def test_accepts_correct_axes(good_fig):
    assert check_axis_units(good_fig, x_expected_range=(-200, 800),
                            x_label_contains="ms", y_label_contains="µV")


def test_accepts_correct_mask(good_fig, data):
    t, _, _, _, sig = data
    assert check_mask_matches(good_fig, t * 1000, sig) is not None


# --- 2. the checks must catch a corrupted figure ------------------------------------------------

def test_catches_wrong_channel(data):
    t, truth, subj, _, _ = data
    fig, ax = plt.subplots()
    ax.plot(t * 1000, subj[3])                       # one subject, not the average
    with pytest.raises(FigureFidelityError):
        check_line(ax, truth)
    plt.close(fig)


def test_catches_sd_band_captioned_as_sem(data):
    t, truth, _, sd, _ = data
    fig, ax = plt.subplots()
    ax.plot(t * 1000, truth)
    ax.fill_between(t * 1000, truth - sd, truth + sd)   # SD, sqrt(n) too wide for a SEM caption
    with pytest.raises(FigureFidelityError):
        check_errorband_is(ax, truth, sd, kind="sem", n=N_SUB)
    plt.close(fig)


def test_catches_axis_unit_mismatch(data):
    t, truth, *_ = data
    fig, ax = plt.subplots()
    ax.plot(t, truth)                                 # seconds on the axis
    ax.set_xlabel("time (ms)")                        # milliseconds in the label
    with pytest.raises(FigureFidelityError):
        check_axis_units(ax, x_expected_range=(-200, 800))
    plt.close(fig)


def test_catches_mask_on_the_wrong_window(data):
    t, truth, _, _, sig = data
    fig, ax = plt.subplots()
    ax.plot(t * 1000, truth)
    ax.axvspan(100, 250, alpha=0.2)                   # MMN window shaded on an N400 figure
    with pytest.raises(FigureFidelityError):
        check_mask_matches(ax, t * 1000, sig)
    plt.close(fig)


def test_catches_a_band_that_is_sem_when_sd_was_claimed(data):
    """The error is symmetric: too NARROW a band is as wrong as too wide."""
    t, truth, _, sd, _ = data
    fig, ax = plt.subplots()
    ax.plot(t * 1000, truth)
    ax.fill_between(t * 1000, truth - sd / np.sqrt(N_SUB), truth + sd / np.sqrt(N_SUB))
    with pytest.raises(FigureFidelityError):
        check_errorband_is(ax, truth, sd, kind="sd")
    plt.close(fig)


# --- regressions from the 2026-09-14 external review ---------------------------------------------
# The checker's absolute 1e-9 tolerance was meaningless for quantities of order 1e-12 (resting
# alpha power in V^2/Hz): a zero line and an SD-labelled-SEM band both passed. And the mask check
# compared only the outermost endpoints, so one span bridging two significant intervals passed.

def _alpha_scale():
    import numpy as np
    return np.linspace(1.27e-12, 2.56e-10, 50)               # the committed resting alpha-power range


def test_zero_line_is_rejected_at_psd_scale():
    import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from figure_fidelity import check_line, FigureFidelityError
    y = _alpha_scale()
    fig, ax = plt.subplots(); ax.plot(np.arange(50), np.zeros(50))
    with pytest.raises(FigureFidelityError):
        check_line(ax, y)
    ax.plot(np.arange(50), y)
    assert check_line(ax, y) is not None                     # the correct line still passes
    plt.close(fig)


def test_sd_band_captioned_sem_is_rejected_at_psd_scale():
    import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from figure_fidelity import check_errorband_is, FigureFidelityError
    y = _alpha_scale(); sd = 0.3 * y; x = np.arange(50)
    fig, ax = plt.subplots(); ax.fill_between(x, y - sd, y + sd)          # an SD band
    with pytest.raises(FigureFidelityError):
        check_errorband_is(ax, y, sd, kind="sem", n=20)                    # captioned SEM -> wrong
    assert check_errorband_is(ax, y, sd, kind="sd") is not None
    plt.close(fig)


def test_one_span_bridging_two_significant_intervals_is_rejected():
    import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from figure_fidelity import check_mask_matches, FigureFidelityError
    t = np.arange(180) / 256.0; sig = np.zeros(180, bool); sig[20:50] = True; sig[95:120] = True
    fig, ax = plt.subplots(); ax.axvspan(t[20], t[119], alpha=0.2)         # bridges 45 samples
    with pytest.raises(FigureFidelityError):
        check_mask_matches(ax, t, sig)
    fig2, ax2 = plt.subplots(); ax2.axvspan(t[20], t[49], alpha=0.2); ax2.axvspan(t[95], t[119], alpha=0.2)
    assert check_mask_matches(ax2, t, sig)                                  # two correct spans pass
    plt.close(fig); plt.close(fig2)


def test_null_mask_rejects_significance_shading():
    """A null result must not carry significance shading; declared window/baseline spans are fine."""
    import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from figure_fidelity import check_mask_matches, FigureFidelityError
    t = np.linspace(-0.2, 0.5, 141); sig = np.zeros_like(t, dtype=bool)
    fig, ax = plt.subplots(); ax.axvspan(0.10, 0.25, alpha=0.2)            # analysis window only
    assert check_mask_matches(ax, t, sig, ignore=[(0.10, 0.25)]) is True
    ax.axvspan(0.15, 0.20, alpha=0.3)                                        # stray significance span
    with pytest.raises(FigureFidelityError):
        check_mask_matches(ax, t, sig, ignore=[(0.10, 0.25)])
    fig2, ax2 = plt.subplots(); ax2.axvspan(0.10, 0.25, alpha=0.2)
    with pytest.raises(FigureFidelityError):                                # undeclared span on a null mask
        check_mask_matches(ax2, t, sig)
    plt.close("all")
