"""Normalize symbolic AntroPy LZ counts once, using the declared alphabet."""
import numpy as np


def symbolic_lzc(symbols, *, alphabet_size):
    """Return count and c*log_base(n)/n, not a correction to a normalized value.

    Supply the approved theoretical alphabet (e.g. 2 or m!), or the explicit
    string 'observed' to reproduce AntroPy's observed-alphabet convention.
    AntroPy is used only for its unnormalized parse count. Inputs are integer
    symbol IDs, already constructed under the approved symbolization/tie policy.
    """
    import antropy

    sequence = np.asarray(symbols)
    if sequence.ndim != 1 or len(sequence) < 2 or sequence.dtype.kind not in 'biu':
        raise ValueError('Provide at least two integer symbols, not continuous EEG samples')
    # Compact IDs preserve the symbolic sequence, avoiding a dependence on its
    # arbitrary numeric codes. Do not re-symbolize a continuous signal here.
    unique, compact = np.unique(sequence, return_inverse=True)
    observed = len(unique)
    if alphabet_size == 'observed':
        base = max(2, observed)
        policy = 'observed_alphabet_with_minimum_2'
    elif (isinstance(alphabet_size, (int, np.integer)) and alphabet_size >= 2
          and alphabet_size >= observed):
        base = int(alphabet_size)
        policy = 'declared_alphabet'
    else:
        raise ValueError('Declare alphabet_size >= observed symbols and >=2, or explicit observed')
    count = int(antropy.lziv_complexity(compact, normalize=False))
    n = len(sequence)
    value = float(count * np.log(n) / (n * np.log(base)))
    return dict(value=value, raw_count=count, n_symbols=n, observed_alphabet=observed,
                normalization_base=base, normalization_policy=policy,
                normalization='c*log_base(n)/n', backend='antropy',
                backend_version=antropy.__version__)


def check_normalized_complexity(values, *, metric):
    """Validate these specific definitions; never clip finite-sequence LZC to 1.

    SampEn/ApEn and other metrics retain their own estimator/status contracts.
    This check only accepts computed values, not unavailable placeholders.
    """
    values = np.asarray(values, float)
    if metric not in ('lzc', 'plzc', 'pe', 'nsc'):
        raise ValueError('Use the requested metric-specific validation contract')
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError('Computed complexity must be finite and nonnegative for this definition')
    if metric in ('pe', 'nsc') and np.any(values > 1):
        raise ValueError('This normalized entropy definition must lie within [0,1]')
