"""Numerical comparison support for library regression tests."""
import numpy as np


def lin_ccc(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    mx, my = x.mean(), y.mean()
    sx, sy = x.var(), y.var()
    cov = ((x - mx) * (y - my)).mean()
    return float(2 * cov / (sx + sy + (mx - my) ** 2))
