"""Compare the shipped tree counter with independent direct pair comparisons."""
from pathlib import Path
import runpy

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sample_entropy = runpy.run_path(str(
    ROOT / 'skills/eeg-complexity/scripts/sample_entropy.py'))['sample_entropy']


def direct_counts(x, m, r_fraction, closed):
    r = r_fraction * np.std(x, ddof=0)
    n = len(x) - m
    counts = []
    for width in (m, m + 1):
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                distance = max(abs(x[i + k] - x[j + k]) for k in range(width))
                count += distance <= r if closed else distance < r
        counts.append(count)
    return counts


@pytest.mark.parametrize('m', [1, 2, 3])
@pytest.mark.parametrize('closed', [True, False])
@pytest.mark.parametrize('fixture', ['random', 'periodic', 'repeated', 'constant'])
def test_counts_match_direct_comparisons(m, closed, fixture):
    x = {
        'random': np.random.default_rng(42).normal(size=90),
        'periodic': np.sin(np.arange(90) * 0.13),
        'repeated': np.tile([0., 1., 1., 0.], 20),
        'constant': np.ones(80),
    }[fixture]
    b, a = direct_counts(x, m, 0.2, closed)
    result = sample_entropy(x, m, 0.2, closed=closed)
    assert result['matching_pairs_m'] == b
    assert result['matching_pairs_m_plus_1'] == a
    assert result['templates'] == len(x) - m
    if a and b:
        assert result['sample_entropy'] == pytest.approx(-np.log(a / b), abs=1e-14)
    else:
        assert np.isnan(result['sample_entropy'])


def test_exact_radius_boundary_is_a_real_option():
    x = np.tile([0., 1.], 30)
    inclusive = sample_entropy(x, r_fraction=2, closed=True)
    strict = sample_entropy(x, r_fraction=2, closed=False)
    assert inclusive['tolerance'] == strict['tolerance'] == 1
    assert inclusive['matching_pairs_m'] > strict['matching_pairs_m']
    assert [strict['matching_pairs_m'], strict['matching_pairs_m_plus_1']] == direct_counts(x, 2, 2, False)


def test_documented_loading_example_executes():
    text = (ROOT / 'skills/eeg-complexity/references/sample-entropy.md').read_text(encoding='utf-8-sig')
    code = text.split('```python\n', 1)[1].split('```', 1)[0]
    x = np.random.default_rng(7).normal(size=200)
    namespace = {'AEA_ROOT': ROOT, 'x': x}
    exec(compile(code, 'sample-entropy.md', 'exec'), namespace)
    np.testing.assert_equal(namespace['result'], sample_entropy(x))
