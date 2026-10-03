"""Smoke tests for the library APIs each AEA skill generates code against.

These do NOT validate scientific correctness — they assert that the *exact*
MNE / pycrostates / mne-connectivity / specparam / sklearn calls documented in the
``skills/eeg-*/SKILL.md`` files still import and run against the installed package
versions, on tiny SYNTHETIC data (no dataset download). Their job is to catch silent
**API drift** (the failure mode that otherwise surfaces in a user's analysis):
e.g. ``pycrostates.metrics`` being removed, ``specparam`` dropping ``aperiodic_params_``,
or MNE renaming a function.

Optional dependencies are guarded with ``importorskip`` so the suite runs on the core
``environment.yml`` env and simply skips the optional-skill checks when those libs are absent.

Run::

    conda run -n aeais python -m pytest tools/tests/test_skill_apis.py -v
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # headless: eeg-figure smoke test

import numpy as np
import pytest
import mne

mne.set_log_level("ERROR")
SFREQ = 250.0


@pytest.fixture(scope="module")
def raw():
    """32-ch, 30 s synthetic EEG on a real 10-20 montage (positions valid)."""
    montage = mne.channels.make_standard_montage("standard_1020")
    ch_names = [c for c in montage.ch_names if c not in ("T3", "T4", "T5", "T6")][:32]
    n = int(SFREQ * 30)
    rng = np.random.RandomState(42)
    t = np.arange(n) / SFREQ
    data = rng.randn(len(ch_names), n) * 1e-5
    data += (5e-6 * np.sin(2 * np.pi * 10 * t))[None, :]  # 10 Hz alpha
    info = mne.create_info(ch_names, SFREQ, "eeg")
    r = mne.io.RawArray(data, info)
    r.set_montage(montage)
    r.set_eeg_reference("average", projection=False)
    return r


@pytest.fixture(scope="module")
def epochs(raw):
    """Fixed-length epochs with a synthetic 2-condition events structure."""
    ep = mne.make_fixed_length_epochs(raw, duration=1.0, overlap=0.0, preload=True)
    # tag alternating epochs as two conditions for ERP/decoding
    ev = ep.events.copy()
    ev[1::2, 2] = 2
    ep.events = ev
    ep.event_id = {"a": 1, "b": 2}
    return ep


# --- eeg-preprocess ----------------------------------------------------------
def test_preprocess_api(raw):
    r = raw.copy().filter(1.0, 40.0, verbose=False)
    r.set_eeg_reference("average", projection=False)
    r.info["bads"] = [r.ch_names[0]]
    r.interpolate_bads(reset_bads=True)
    assert r.info["bads"] == []


def test_preprocess_ransac_pyprep(raw):
    pyprep = pytest.importorskip("pyprep")
    nc = pyprep.NoisyChannels(raw.copy().filter(1.0, 40.0, verbose=False), random_state=42)
    nc.find_bad_by_correlation()  # fast; RANSAC path shares the same object API
    assert isinstance(nc.get_bads(), list)


# --- eeg-ica -----------------------------------------------------------------
@pytest.fixture(scope="module")
def fitted_ica(raw):
    """One extended-Infomax fit shared by the ICA and ICLabel tests.

    These two tests previously fitted the SAME ICA independently, at ~25 s each -- 77% of this
    file's runtime for one duplicated computation. That matters here beyond tidiness: this file is
    what an external tester runs, and docs/FIRST_EXTERNAL_TEST.md promises "about 5 minutes". A
    slower laptop was at risk of blowing through that.

    Both tests need the same 1 Hz high-passed copy, so the fixture returns both.
    """
    r = raw.copy().filter(1.0, None, verbose=False)
    ica = mne.preprocessing.ICA(
        n_components=15, method="infomax", random_state=42,
        max_iter="auto", fit_params=dict(extended=True),
    )
    ica.fit(r)
    return ica, r


def test_ica_api(fitted_ica):
    ica, r = fitted_ica
    assert ica.n_components_ == 15
    # documented find_bads_* path (muscle works on EEG without EOG/ECG refs)
    idx, scores = ica.find_bads_muscle(r)
    assert isinstance(idx, list)


def test_iclabel_api(fitted_ica):
    pytest.importorskip("mne_icalabel")
    from mne_icalabel import label_components
    ica, r = fitted_ica
    labels = label_components(r, ica, method="iclabel")
    assert len(labels["labels"]) == ica.n_components_


# --- eeg-epoch ---------------------------------------------------------------
def test_epoch_api(raw):
    ep = mne.make_fixed_length_epochs(raw, duration=2.0, overlap=0.5, preload=True)
    assert len(ep) > 0
    autoreject = pytest.importorskip("autoreject")
    thr = autoreject.get_rejection_threshold(ep, random_state=42)
    assert "eeg" in thr


# --- eeg-erp -----------------------------------------------------------------
def test_erp_api(epochs):
    evoked = epochs["a"].average()
    ch, lat, amp = evoked.get_peak(tmin=0.0, tmax=0.5, return_amplitude=True)
    assert ch in evoked.ch_names
    # mean amplitude in a window (the eeg-erp measurement path)
    seg = evoked.copy().crop(0.1, 0.2).data.mean(axis=1)
    assert seg.shape[0] == len(evoked.ch_names)


# --- eeg-tfr -----------------------------------------------------------------
def test_tfr_api(epochs):
    freqs = np.arange(4.0, 30.0, 2.0)
    tfr = epochs.compute_tfr(method="morlet", freqs=freqs, n_cycles=freqs / 2.0,
                             return_itc=False, average=True)
    assert tfr.data.ndim == 3
    # Hilbert-on-narrowband path (eeg-tfr high-time-resolution route)
    analytic = epochs.copy().filter(8, 12, verbose=False).apply_hilbert()
    assert np.iscomplexobj(analytic.get_data())


# --- eeg-spectral ------------------------------------------------------------
def test_spectral_welch_api(raw):
    from mne.time_frequency import psd_array_welch
    data = raw.get_data()
    n_per_seg = int(2 * SFREQ)
    psd, freqs = psd_array_welch(data, SFREQ, fmin=1, fmax=40, n_fft=n_per_seg,
                                 n_per_seg=n_per_seg, n_overlap=n_per_seg // 2,
                                 window="hann", verbose=False)
    assert psd.shape[0] == data.shape[0] and freqs[0] >= 1


def test_spectral_specparam_api():
    pytest.importorskip("specparam")
    from specparam import SpectralModel
    f = np.linspace(1, 45, 200)
    p = 1.0 / f ** 1.5 + 0.3 * np.exp(-((f - 10) ** 2) / 2)
    sm = SpectralModel(aperiodic_mode="fixed")
    sm.fit(f, p, [1, 40])
    # version-robust extraction used by eeg-spectral / eeg-complexity
    exponent = sm.get_params("aperiodic", "exponent")
    assert np.isfinite(exponent)


# --- eeg-stats ---------------------------------------------------------------
def test_stats_cluster_and_fdr_api(raw):
    from mne.stats import (spatio_temporal_cluster_1samp_test,
                           fdr_correction, f_mway_rm, permutation_cluster_test)
    rng = np.random.RandomState(0)
    n_subj, n_times, n_ch = 12, 20, len(raw.ch_names)
    X = rng.randn(n_subj, n_times, n_ch)
    adjacency, _ = mne.channels.find_ch_adjacency(raw.info, ch_type="eeg")
    T_obs, clusters, p, H0 = spatio_temporal_cluster_1samp_test(
        X, n_permutations=50, adjacency=adjacency, seed=42, verbose=False)
    assert T_obs.shape == (n_times, n_ch)
    reject, p_corr = fdr_correction(rng.uniform(0, 0.1, 30), alpha=0.05)
    assert reject.shape == (30,)
    # factorial within-subject ANOVA (eeg-stats f_mway_rm path)
    fvals, pvals = f_mway_rm(rng.randn(n_subj, 4), factor_levels=[2, 2], effects="A")
    assert np.all(np.isfinite(fvals))


# --- eeg-connectivity --------------------------------------------------------
def test_connectivity_api(raw):
    mnc = pytest.importorskip("mne_connectivity")
    conn_epochs = mne.make_fixed_length_epochs(raw, duration=4.0, overlap=0.0, preload=True)
    con = mnc.spectral_connectivity_epochs(
        conn_epochs, method="wpli2_debiased", mode="multitaper",
        fmin=8.0, fmax=13.0, faverage=True, verbose=False)
    assert con.get_data(output="dense").ndim >= 2
    # time-resolved estimator (capability eeg-connectivity adds); few cycles so the
    # Morlet wavelet fits inside the epoch
    freqs = np.arange(8.0, 13.0, 1.0)
    cont = mnc.spectral_connectivity_time(conn_epochs, freqs=freqs, method="coh",
                                          mode="cwt_morlet", n_cycles=3.0, verbose=False)
    assert cont is not None


def test_connectivity_csd_api(raw):
    csd = mne.preprocessing.compute_current_source_density(raw.copy())
    assert csd.get_data().shape == raw.get_data().shape


# --- eeg-microstate ----------------------------------------------------------
def test_microstate_api(raw):
    pytest.importorskip("pycrostates")
    from pycrostates.cluster import ModKMeans
    from pycrostates import segmentation as pseg
    ModK = ModKMeans(n_clusters=4, random_state=42)
    ModK.fit(raw.copy().filter(2, 20, verbose=False), n_jobs=1, verbose=False)
    seg = ModK.predict(raw, verbose=False)
    params = seg.compute_parameters()           # NOT pycrostates.metrics (removed)
    assert isinstance(params, dict) and len(params) > 0
    assert hasattr(pseg, "compute_transition_matrix")
    # temporal params (duration/occurrence/coverage) come from compute_parameters(),
    # NOT pycrostates.metrics (which holds cluster-quality scores like silhouette).
    import pycrostates.metrics as pm
    assert hasattr(pm, "silhouette")


# --- eeg-complexity ----------------------------------------------------------
def test_complexity_antropy_api():
    ant = pytest.importorskip("antropy")
    x = np.random.RandomState(0).randn(1250)
    assert np.isfinite(ant.perm_entropy(x, order=3, delay=1, normalize=True))
    assert np.isfinite(ant.lziv_complexity((x > np.median(x)).astype(int), normalize=True))
    assert np.isfinite(ant.spectral_entropy(x, sf=SFREQ, method="welch", normalize=True))
    assert np.isfinite(ant.detrended_fluctuation(x))


def test_complexity_neurokit_api():
    nk = pytest.importorskip("neurokit2")
    x = np.random.RandomState(0).randn(1250)
    r = 0.2 * np.std(x)
    assert np.isfinite(nk.entropy_sample(x, dimension=2, tolerance=r)[0])
    assert np.isfinite(nk.complexity_lempelziv(x, dimension=4, delay=1, permutation=True)[0])


def test_complexity_spatial_numpy(raw):
    # Omega / NSC — pure numpy, always available (eeg-complexity Phase G)
    data = raw.get_data()
    ev = np.linalg.eigvalsh(np.cov(data))
    ev = ev[ev > 0]
    p = ev / ev.sum()
    nsc = (-np.sum(p * np.log(p))) / np.log(data.shape[0])
    assert 0.0 <= nsc <= 1.0


# --- eeg-decoding ------------------------------------------------------------
def test_decoding_api(epochs):
    # scikit-learn is NOT a core mne dependency (mne needs matplotlib/numpy/scipy/pooch/...),
    # so an unguarded import here fails the suite for anyone who installed only what the
    # first-external-test instructions ask for. Skip instead.
    pytest.importorskip("sklearn")
    from mne.decoding import SlidingEstimator, GeneralizingEstimator, CSP, Vectorizer  # noqa: F401
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import GroupKFold, permutation_test_score
    X = epochs.get_data()
    y = epochs.events[:, 2]
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=200))
    sl = SlidingEstimator(clf, scoring="accuracy")
    from mne.decoding import cross_val_multiscore
    scores = cross_val_multiscore(sl, X, y, cv=3, n_jobs=1)
    assert scores.shape[0] == 3
    # leakage-safe group CV + corrected permutation p exist (eeg-decoding rules)
    assert GroupKFold(n_splits=2) is not None and callable(permutation_test_score)


def test_decoding_mne_features_api():
    mf = pytest.importorskip("mne_features")
    from mne_features.feature_extraction import extract_features
    X = np.random.RandomState(0).randn(4, 8, 500)
    feats = extract_features(X, SFREQ, ["samp_entropy", "higuchi_fd"])
    assert feats.shape[0] == 4


# --- eeg-source (API presence: full forward/inverse needs FreeSurfer) --------
def test_source_api_present():
    import mne.beamformer as bf
    import mne.minimum_norm as mn
    for fn in ("make_lcmv", "apply_lcmv", "make_dics", "apply_dics_csd"):
        assert hasattr(bf, fn), f"mne.beamformer.{fn} missing"
    for fn in ("make_inverse_operator", "apply_inverse"):
        assert hasattr(mn, fn), f"mne.minimum_norm.{fn} missing"
    # ad-hoc covariance is runnable without FreeSurfer
    info = mne.create_info(["Fz", "Cz", "Pz"], SFREQ, "eeg")
    assert mne.make_ad_hoc_cov(info) is not None


# --- eeg-behavior ------------------------------------------------------------
def test_behavior_mixedlm_api():
    sm = pytest.importorskip("statsmodels.formula.api")
    pytest.importorskip("pandas")   # statsmodels pulls it in, but do not rely on a transitive dep
    import pandas as pd
    rng = np.random.RandomState(0)
    df = pd.DataFrame(dict(y=rng.randn(40), x=rng.randn(40), subj=np.repeat(np.arange(10), 4)))
    res = sm.mixedlm("y ~ x", df, groups=df["subj"]).fit()
    assert res.params is not None


# --- eeg-bids ----------------------------------------------------------------
def test_bids_api(raw, tmp_path):
    mne_bids = pytest.importorskip("mne_bids")
    from mne_bids import BIDSPath, write_raw_bids
    bp = BIDSPath(subject="01", task="rest", datatype="eeg", root=str(tmp_path))
    assert bp.subject == "01" and callable(write_raw_bids)   # mne-bids API present
    pytest.importorskip("pybv")                              # writing EEG → BIDS needs pybv
    r = raw.copy()
    r.info["line_freq"] = 50.0
    write_raw_bids(r, bp, overwrite=True, allow_preload=True, format="BrainVision", verbose=False)
    assert any(tmp_path.rglob("*.vhdr"))


# --- eeg-figure --------------------------------------------------------------
def test_figure_api(epochs):
    import matplotlib.pyplot as plt
    evoked = epochs["a"].average()
    fig = evoked.plot(show=False)
    assert fig is not None
    fig2 = evoked.plot_topomap(times=[0.1], show=False)
    assert fig2 is not None
    plt.close("all")


# --- eeg-tfr: ITPC / ITLC (added insight) ---
def test_tfr_itpc_api(epochs):
    freqs = np.arange(6.0, 12.0, 2.0)
    power, itc = epochs.compute_tfr(method="morlet", freqs=freqs, n_cycles=3.0,
                                    return_itc=True, average=True)
    assert itc.data.shape[0] == len(epochs.ch_names)
    assert itc.data.min() >= -1e-6 and itc.data.max() <= 1.0 + 1e-6   # ITPC in [0,1]


# --- eeg-decoding: per-fold sensitivity / specificity reporting (added insight) ---
def test_decoding_metrics_api():
    pytest.importorskip("sklearn")   # not a core mne dependency — see test_decoding_api
    from sklearn.metrics import confusion_matrix, balanced_accuracy_score, roc_auc_score
    y = np.array([0, 0, 1, 1, 0, 1, 1, 0])
    yp = np.array([0, 1, 1, 1, 0, 0, 1, 0])
    tn, fp, fn, tp = confusion_matrix(y, yp).ravel()
    sens = tp / (tp + fn)
    spec = tn / (tn + fp)
    assert 0 <= sens <= 1 and 0 <= spec <= 1
    assert 0 <= balanced_accuracy_score(y, yp) <= 1
    assert 0 <= roc_auc_score(y, yp) <= 1


# --- eeg-spectral: parametric AR / Yule-Walker PSD (added insight) ---
def test_spectral_ar_api(raw):
    pytest.importorskip("statsmodels")
    from statsmodels.regression.linear_model import yule_walker
    x = raw.get_data()[0]
    x = x - x.mean()
    rho, sigma = yule_walker(x, order=20, method="mle")
    f = np.linspace(0, SFREQ / 2, 256)
    a = np.r_[1.0, -rho]
    H = 1.0 / np.abs(np.exp(-1j * 2 * np.pi * np.outer(f, np.arange(len(a))) / SFREQ) @ a)
    psd = (sigma ** 2 / SFREQ) * H ** 2
    assert psd.shape == (256,) and np.all(np.isfinite(psd)) and np.all(psd >= 0)


# --- eeg-connectivity PAC: pure-numpy circular Rayleigh test + optional comodulogram ---
def test_connectivity_pac_rayleigh_numpy():
    rng = np.random.RandomState(0)
    phases = rng.vonmises(mu=0.5, kappa=2.0, size=200)   # concentrated → significant
    R = np.abs(np.mean(np.exp(1j * phases)))
    n = phases.size
    z = n * R ** 2
    p = np.exp(-z) * (1 + (2 * z - z ** 2) / (4 * n))
    assert 0 <= R <= 1 and p < 0.05


def test_connectivity_pac_comodulogram_optional():
    pytest.importorskip("pactools")
    from pactools import Comodulogram  # noqa: F401
    assert True


# --- eeg-qc ------------------------------------------------------------------
def test_qc_api(raw, epochs):
    # find_bad_channels_lof needs scikit-learn, which is NOT a core mne dependency. mne raises
    # RuntimeError rather than ImportError for it, so a plain try/except ImportError would not
    # catch it either -- gate the whole test on the module being importable.
    pytest.importorskip("sklearn", reason="find_bad_channels_lof (LOF) requires scikit-learn")
    # annotate_amplitude: flat + high-amplitude segment detection
    annots, flat = mne.preprocessing.annotate_amplitude(
        raw, peak=dict(eeg=120e-6), flat=dict(eeg=1e-8),
        bad_percent=50.0, min_duration=0.005, verbose=False)
    assert isinstance(flat, list)
    # LOF bad-channel detection (eeg-qc corroborates pyprep)
    bads = mne.preprocessing.find_bad_channels_lof(raw, picks="eeg", verbose=False)
    assert isinstance(bads, list)
    # PSD for SNR / line-noise ratio
    psd = raw.compute_psd(method="welch", fmin=1, fmax=40, verbose=False)
    assert psd.get_data().shape[0] == len(raw.ch_names)
    # rejection-rate reporting from the drop log
    assert isinstance(epochs.drop_log_stats(), float)


# --- eeg-group-compare -------------------------------------------------------
def test_group_compare_api(raw):
    from mne.stats import spatio_temporal_cluster_test
    rng = np.random.RandomState(1)
    n_ch = len(raw.ch_names)
    adjacency, _ = mne.channels.find_ch_adjacency(raw.info, ch_type="eeg")
    # between-group second level: two groups of subjects, (subj, times, ch)
    g1 = rng.randn(10, 15, n_ch)
    g2 = rng.randn(12, 15, n_ch) + 0.1
    T_obs, clusters, p, H0 = spatio_temporal_cluster_test(
        [g1, g2], n_permutations=50, adjacency=adjacency, seed=42, verbose=False)
    assert T_obs.shape == (15, n_ch)
    # repeated-measures ANOVA (statsmodels path; optional dep)
    sm_anova = pytest.importorskip("statsmodels.stats.anova")
    pytest.importorskip("pandas")
    import pandas as pd
    df = pd.DataFrame({"subj": np.repeat(np.arange(10), 2),
                       "cond": np.tile(["a", "b"], 10), "y": rng.randn(20)})
    aov = sm_anova.AnovaRM(df, "y", "subj", within=["cond"]).fit()
    assert aov.anova_table.shape[0] == 1
