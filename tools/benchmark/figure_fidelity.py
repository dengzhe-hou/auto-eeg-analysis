#!/usr/bin/env python
"""Does the figure show the numbers it claims?

Every other check in this project asks whether a computed value is right. A figure is where those
values stop being checked: `eeg-figure` prescribes a written sanity checklist, but the only
machine-verified assertion anywhere was `assert fig is not None`. A plot that draws the wrong
channel, the wrong time window, or SD-shaped error bars under a caption saying SEM is wrong in a
way no numeric test can see, and it is the artefact a reader actually believes.

So: read the data back out of the matplotlib artists and compare it to the arrays the figure was
supposed to display.

What this catches
  - wrong channel / ROI            (plotted line != the intended source array)
  - wrong time window or units     (x-axis in samples or seconds when the caption says ms)
  - error bars that are SD when the caption says SEM, and vice versa
  - a shaded significance mask that does not correspond to the significant samples
  - an axis label that names a different quantity than the one plotted

What this does NOT do
  It says nothing about whether the figure is a *good* figure -- legibility, colour, print size.
  Those are judgement, and `eeg-figure`'s checklist keeps them. This checks correspondence only.
"""
from __future__ import annotations

import numpy as np

TOL = 1e-9   # relative to the data scale -- see _atol(). An ABSOLUTE 1e-9 silently accepted a zero
             # line in place of resting alpha power (1e-12..1e-10 V^2/Hz): external review, 2026-09-14.


def _atol(*arrays, rel=TOL):
    """Absolute tolerance scaled to the data: rel x the largest magnitude among the arrays.

    Plotted EEG quantities span ~1e-12 (power spectral density in V^2/Hz) to ~1e2 (samples, ms). A
    fixed absolute tolerance is meaningless across that range; a scale-relative one is not.
    """
    scale = max((float(np.max(np.abs(a))) for a in arrays if np.size(a)), default=0.0)
    return rel * max(scale, np.finfo(float).tiny)


class FigureFidelityError(AssertionError):
    pass


def _lines(ax):
    return [ln for ln in ax.get_lines() if ln.get_xdata().size]


def check_line(ax, expected_y, *, expected_x=None, label=None, rtol=1e-6, atol=None):
    """A line in `ax` must reproduce `expected_y` point-for-point.

    Matching by label when given, else by trying every line: the assertion is that AT LEAST ONE
    drawn line is the array we meant to draw. Failing to find one is the finding.
    """
    exp_y = np.asarray(expected_y, dtype=float).ravel()
    atol_y = _atol(exp_y) if atol is None else atol
    cands = _lines(ax)
    if label is not None:
        cands = [ln for ln in cands if ln.get_label() == label] or cands
    for ln in cands:
        y = np.asarray(ln.get_ydata(), dtype=float).ravel()
        if y.shape != exp_y.shape:
            continue
        if not np.allclose(y, exp_y, rtol=rtol, atol=atol_y):
            continue
        if expected_x is not None:
            x = np.asarray(ln.get_xdata(), dtype=float).ravel()
            exp_x = np.asarray(expected_x, dtype=float).ravel()
            atol_x = _atol(exp_x) if atol is None else atol
            if x.shape != exp_x.shape or not np.allclose(x, exp_x, rtol=rtol, atol=atol_x):
                continue
        return ln
    raise FigureFidelityError(
        f"no line in this axes reproduces the expected array "
        f"(n={exp_y.size}, range {exp_y.min():.4g}..{exp_y.max():.4g}); "
        f"drawn lines have shapes {[np.asarray(l.get_ydata()).shape for l in _lines(ax)]}"
    )


def check_errorband_is(ax, centre, spread, *, kind, n=None):
    """A shaded band must be centre +/- the spread it claims.

    `kind` is 'sd' or 'sem'. Passing the wrong one is the point: an SD band under a SEM caption is
    sqrt(n) too wide and is one of the easiest errors to publish, because the figure looks fine.
    """
    if kind not in {"sd", "sem"}:
        raise ValueError("kind must be 'sd' or 'sem'")
    centre = np.asarray(centre, dtype=float).ravel()
    spread = np.asarray(spread, dtype=float).ravel()
    if kind == "sem":
        if n is None:
            raise ValueError("kind='sem' needs n")
        spread = spread / np.sqrt(n)
    want_lo, want_hi = centre - spread, centre + spread

    # matplotlib lays a fill_between polygon out as: one leading vertex, then n lower-bound
    # points, then n upper-bound points in reverse, then closing vertices. Rather than hardcode
    # that offset -- which would silently break when matplotlib changes it -- search for a
    # contiguous window of the right length that matches. The tolerance is relative to the band's
    # own scale: at an absolute 1e-9 an SD band and a SEM band were indistinguishable for
    # quantities of order 1e-12 (external review, 2026-09-14).
    n_pts = centre.size
    tol = _atol(want_lo, want_hi, spread)

    def _has_window(col, want):
        for k in range(0, col.size - n_pts + 1):
            w = col[k:k + n_pts]
            if np.allclose(w, want, rtol=1e-6, atol=tol) or np.allclose(w[::-1], want, rtol=1e-6, atol=tol):
                return True
        return False

    for coll in ax.collections:
        try:
            paths = coll.get_paths()
        except Exception:                                    # noqa: BLE001
            continue
        for pth in paths:
            y = pth.vertices[:, 1]
            if y.size < 2 * n_pts:
                continue
            if _has_window(y, want_lo) and _has_window(y, want_hi):
                return coll
    raise FigureFidelityError(
        f"no shaded band matches centre +/- {kind.upper()}"
        + (f" (n={n})" if kind == "sem" else "")
        + ". A band that is sqrt(n) too wide is an SD band captioned as SEM."
    )


def check_axis_units(ax, *, x_expected_range=None, x_label_contains=None,
                     y_label_contains=None):
    """The axis must span what the data span, and say what it is."""
    problems = []
    if x_expected_range is not None:
        lo, hi = ax.get_xlim()
        want_lo, want_hi = x_expected_range
        # the drawn range must at least cover the data; a 10x unit error fails this immediately
        if not (lo <= want_lo + abs(want_lo) * 0.05 + 1e-9
                and hi >= want_hi - abs(want_hi) * 0.05 - 1e-9):
            problems.append(f"x-limits {lo:.4g}..{hi:.4g} do not cover the data "
                            f"{want_lo:.4g}..{want_hi:.4g} — a unit mismatch (s vs ms vs samples) "
                            f"looks exactly like this")
    for got, want, which in ((ax.get_xlabel(), x_label_contains, "x"),
                             (ax.get_ylabel(), y_label_contains, "y")):
        if want and want.lower() not in (got or "").lower():
            problems.append(f"{which}-label {got!r} does not mention {want!r}")
    if problems:
        raise FigureFidelityError("; ".join(problems))
    return True


def _runs(mask):
    """Contiguous True runs of a boolean mask as (start_index, end_index) pairs, inclusive."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    ends = np.concatenate((idx[breaks], [idx[-1]]))
    return list(zip(starts.tolist(), ends.tolist()))


def _drawn_spans(ax):
    """(artist, x_min, x_max) for every shaded span on the axes: Rectangle patches (axvspan) and
    collections (fill_between)."""
    out = []
    for c in ax.collections:
        for pth in getattr(c, "get_paths", lambda: [])():
            x = pth.vertices[:, 0]
            if x.size:
                out.append((c, float(x.min()), float(x.max())))
    for pa in ax.patches:
        try:
            x = pa.get_path().transformed(pa.get_patch_transform()).vertices[:, 0]
        except Exception:                                # noqa: BLE001
            continue
        if x.size:
            out.append((pa, float(x.min()), float(x.max())))
    return out


def check_mask_matches(ax, times, significant, *, atol=None, ignore=()):
    """Shaded significance spans must cover exactly the significant samples -- every run of them.

    The first version compared only the outermost endpoints, so one span bridging two separate
    significant intervals (and the non-significant samples between them) passed. Now every
    contiguous significant run needs a span with its own endpoints, and no drawn span may cover a
    non-significant sample. Endpoint tolerance is half a sample step, whatever the time unit.
    """
    times = np.asarray(times, dtype=float).ravel()
    sig = np.asarray(significant, dtype=bool).ravel()
    step = float(np.min(np.diff(times))) if times.size > 1 else 1.0
    tol = step / 2 if atol is None else atol
    if not sig.any():
        # A null result must not carry significance shading. Spans drawn for other reasons (analysis
        # window, baseline) are declared in ``ignore``; anything else is a false significance span.
        # The first version returned True here without looking at the axes (external review, 2026-09-15).
        stray = [(s_lo, s_hi) for _, s_lo, s_hi in _drawn_spans(ax)
                 if not any(abs(s_lo - lo) <= tol and abs(s_hi - hi) <= tol for lo, hi in ignore)]
        if stray:
            raise FigureFidelityError(
                f"nothing is significant, but shaded spans {[(round(a, 4), round(b, 4)) for a, b in stray][:4]} "
                f"are drawn and are not among the declared non-significance spans {list(ignore)}")
        return True
    runs = [(times[a], times[b]) for a, b in _runs(sig)]

    # A shaded span can be a Rectangle patch (axvspan) or a collection (fill_between). Looking in
    # only one of them makes the check reject correct figures, which is worse than not having it:
    # a check that fails on correct input gets switched off, and then it guards nothing.
    spans = _drawn_spans(ax)
    matched = []
    for lo, hi in runs:
        hit = [a for a, s_lo, s_hi in spans if abs(s_lo - lo) <= tol and abs(s_hi - hi) <= tol]
        if not hit:
            raise FigureFidelityError(
                f"no shaded span covers the significant interval {lo:.4g}..{hi:.4g}; "
                f"spans present: {[(s_lo, s_hi) for _, s_lo, s_hi in spans][:4]}")
        matched.append(hit[0])
    # A span that starts or ends on a significant-interval boundary is a significance span, and
    # must then equal exactly one interval: one span from interval 1's start to interval 2's end
    # bridges the non-significant gap while looking 'covering' by its endpoints. Spans unrelated to
    # those boundaries (epoch background, baseline shading) are somebody else's business.
    for artist, s_lo, s_hi in spans:
        on_boundary = (any(abs(s_lo - lo) <= tol for lo, _ in runs)
                       or any(abs(s_hi - hi) <= tol for _, hi in runs))
        is_one_run = any(abs(s_lo - lo) <= tol and abs(s_hi - hi) <= tol for lo, hi in runs)
        if on_boundary and not is_one_run:
            raise FigureFidelityError(
                f"shaded span {s_lo:.4g}..{s_hi:.4g} starts or ends on a significant interval but "
                f"does not equal one; the significant intervals are "
                f"{[(round(a, 4), round(b, 4)) for a, b in runs]}")
    return matched[0] if len(matched) == 1 else matched
