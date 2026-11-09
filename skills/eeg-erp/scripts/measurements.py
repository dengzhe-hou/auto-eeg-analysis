"""Fractional-area latency with explicitly selected measurement conventions."""
import numpy as np
from scipy.integrate import cumulative_trapezoid


def fractional_area_latency(signal, times, *, fraction, area_mode, polarity,
                            crossing, interpolation):
    """Integrate a supplied ROI trace using trapezoids and locate a crossing.

    No scientific choice has a default. ``signed`` retains opposite-polarity
    samples after orientation; ``positive`` clips the oriented trace at zero;
    ``absolute`` integrates absolute amplitude and requires polarity=None.
    ``first``/``last`` select upward crossings of the target cumulative area.
    ``sample`` returns the right sample; ``linear`` interpolates between the
    sampled cumulative-area values (not the original voltage samples).

    A signed cumulative area need not be monotonic. Do not sort it or use
    searchsorted: that would discard the chronological crossing structure.
    Inputs are already restricted to the approved ROI and measurement window.
    Use this helper only if these integration conventions match the plan.
    """
    signal = np.asarray(signal, dtype=float)
    times = np.asarray(times, dtype=float)
    if (signal.ndim != 1 or times.shape != signal.shape or len(times) < 2
            or not np.isfinite(signal).all() or not np.isfinite(times).all()
            or not np.all(np.diff(times) > 0)):
        raise ValueError("Supply one finite trace and matching increasing times")
    if not np.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError("fraction must be explicitly selected between 0 and 1")
    if area_mode == "absolute":
        if polarity is not None:
            raise ValueError("Absolute area uses polarity=None")
        integrand = np.abs(signal)
    elif area_mode in ("signed", "positive"):
        if polarity not in ("positive", "negative"):
            raise ValueError("Signed/polarity-specific area requires a polarity")
        integrand = signal if polarity == "positive" else -signal
        if area_mode == "positive":
            integrand = np.maximum(integrand, 0)
    else:
        raise ValueError("Select signed, positive or absolute area explicitly")
    if crossing not in ("first", "last"):
        raise ValueError("Select first or last upward crossing explicitly")
    if interpolation not in ("sample", "linear"):
        raise ValueError("Select sample or linear interpolation explicitly")

    cumulative = cumulative_trapezoid(integrand, times, initial=0)
    total = float(cumulative[-1])
    if total <= 0:
        raise ValueError("No positive total area under the selected convention")
    target = float(fraction * total)
    right = np.flatnonzero((cumulative[:-1] < target)
                           & (cumulative[1:] >= target)) + 1
    index = int(right[0] if crossing == "first" else right[-1])
    latency = float(times[index])
    if interpolation == "linear":
        left = index - 1
        weight = (target - cumulative[left]) / (cumulative[index] - cumulative[left])
        latency = float(times[left] + weight * (times[index] - times[left]))
    return {"latency_s": latency, "total_area": total,
            "fraction": float(fraction), "area_mode": area_mode,
            "polarity": polarity, "crossing": crossing,
            "interpolation": interpolation, "integration": "trapezoid"}
