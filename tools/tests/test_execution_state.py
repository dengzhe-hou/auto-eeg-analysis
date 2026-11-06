"""Real-process progress, retained failures and source replay of synthetic EEG."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import mne
import numpy as np
import pytest
from scipy.signal import hilbert

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'skills/eeg-epoch/scripts'))
import replay
from erp import mean_roi_amplitude
from run_continuous_plan import run_plan


def wait_for(read, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = read()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('Test child did not reach the requested state')


def test_replay_saves_completed_steps_while_next_real_child_is_running(tmp_path):
    bundle = tmp_path / 'saved bundle'
    analysis = bundle / 'analysis'; analysis.mkdir(parents=True)
    data = tmp_path / 'data'; data.mkdir()
    (bundle / 'capture.json').write_text(json.dumps({
        'python': replay.platform.python_version(), 'packages': {}, 'data': str(data)}))
    (analysis / 'run.json').write_text(json.dumps({'commands': [
        ['{python}', '-c', "from pathlib import Path; Path(r'{out}/first.txt').write_text('kept')"],
        ['{python}', 'second.py', '{out}']]}))
    (analysis / 'second.py').write_text(
        "from pathlib import Path\nimport sys,time\no=Path(sys.argv[1])\n"
        "while not (o/'release').exists(): time.sleep(.02)\n"
        "(o/'second.txt').write_text('done')\n")
    out = tmp_path / 'out with spaces'
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(replay.run, bundle, out)
        try:
            def second_running():
                p = out / 'execution.json'
                if not p.exists(): return False
                value = json.loads(p.read_text())
                return value if len(value['steps']) == 2 and value['steps'][1]['status'] == 'running' else False
            record = wait_for(second_running)
            assert record['steps'][0]['status'] == 'completed'
            assert record['steps'][0]['exit_code'] == 0
            assert record['steps'][0]['finished_at']
            assert (out / 'first.txt').read_text() == 'kept'
            status = replay.inspect_run(out)
            assert status['recorded_status'] == 'running'
            assert status['coordinator_running'] and status['child_running']
            assert status['active_step']['argv'] == [sys.executable, 'second.py', str(out.resolve())]
        finally:
            out.mkdir(exist_ok=True)
            (out / 'release').write_text('continue test child')
        assert future.result(timeout=10) == 0
    final = json.loads((out / 'execution.json').read_text())
    assert all(s['status'] == 'completed' and s['exit_code'] == 0 for s in final['steps'])


def test_stale_record_distinguishes_dead_coordinator_from_live_child(tmp_path):
    dead = subprocess.Popen([sys.executable, '-c', 'pass']); dead.wait()
    with subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)']) as child:
        try:
            record = {'status': 'running', 'hostname': socket.gethostname(),
                      'coordinator_pid': dead.pid, 'steps': [{'status': 'running', 'pid': child.pid}]}
            (tmp_path / 'execution.json').write_text(json.dumps(record))
            before = (tmp_path / 'execution.json').read_bytes()
            status = replay.inspect_run(tmp_path)
            assert status['coordinator_running'] is False and status['child_running'] is True
            assert (tmp_path / 'execution.json').read_bytes() == before
        finally:
            child.terminate(); child.wait(timeout=5)


def test_status_on_another_host_never_probes_local_pids(tmp_path, monkeypatch):
    (tmp_path / 'execution.json').write_text(json.dumps({
        'status': 'running', 'hostname': 'another-host', 'coordinator_pid': os.getpid(), 'steps': []}))
    monkeypatch.setattr(replay, 'process_running', lambda pid: pytest.fail('wrong host PID query'))
    assert replay.inspect_run(tmp_path)['coordinator_running'] is None


def test_status_cli_does_not_execute_or_rewrite_any_step(tmp_path):
    path = tmp_path / 'execution.json'
    path.write_text(json.dumps({'status': 'failed', 'hostname': socket.gethostname(),
                               'coordinator_pid': os.getpid(), 'steps': []}))
    before = path.read_bytes()
    checked = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/replay.py'),
                              'status', '--out', str(tmp_path)], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)['recorded_status'] == 'failed'
    assert path.read_bytes() == before


@pytest.fixture
def epochs():
    data = np.zeros((4, 2, 101))
    data[:, :, 20:71] = np.array([[1, 2], [5, 6], [3, 4], [7, 8]])[:, :, None] * 1e-6
    return mne.EpochsArray(data, mne.create_info(['Cz', 'Pz'], 100., 'eeg'),
        events=np.array([[100, 0, 1], [300, 0, 2], [500, 0, 1], [700, 0, 2]]),
        event_id={'A': 1, 'B': 2}, tmin=-.2, baseline=None, verbose=False)


@pytest.mark.parametrize('window', [[.1, 1.], [-1., .3]])
def test_erp_rejects_partially_available_window_instead_of_shortening_it(epochs, window):
    with pytest.raises(ValueError, match='exceeds actual epoch range'):
        mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=window)


def test_explicit_roi_is_used_even_when_a_channel_is_marked_bad(epochs):
    epochs._data[1::2, 0, :] += 2e-6
    epochs.info['bads'] = ['Cz']
    measured = mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=[.1, .3])
    assert measured['roi_amplitude_uv'] == pytest.approx(5., abs=1e-12)
    assert epochs.info['bads'] == ['Cz']


def test_erp_preconditions_report_actual_channels_and_types(epochs):
    with pytest.raises(ValueError, match='absent from actual epochs'):
        mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Oz'], window_s=[.1, .3])
    epochs.set_channel_types({'Pz': 'eog'})
    with pytest.raises(ValueError, match='actual types'):
        mean_roi_amplitude(epochs, plus='B', minus='A', roi=['Cz', 'Pz'], window_s=[.1, .3])


def test_nominal_epoch_endpoints_are_allowed_after_normal_sample_rounding():
    ep = mne.EpochsArray(np.zeros((2, 1, 257)), mne.create_info(['Cz'], 256., 'eeg'),
        events=np.array([[300, 0, 1], [800, 0, 2]]), event_id={'A': 1, 'B': 2},
        tmin=-.2, baseline=None, verbose=False)
    assert mean_roi_amplitude(ep, plus='B', minus='A', roi=['Cz'], window_s=[-.2, .8])['roi_amplitude_uv'] == 0.


@pytest.fixture
def raw():
    data = np.random.default_rng(62).normal(size=(2, 400)) * 1e-6
    return mne.io.RawArray(data, mne.create_info(['Cz', 'Pz'], 100., 'eeg'), verbose=False)


def welch_plan():
    return {'analysis_channels': ['Cz', 'Pz'], 'operations': [],
        'required_results': {'status': '', 'explanation': ''},
        'required_evidence': {'channels': '', 'freqs': '', 'psd': ''},
        'welch': {'segment_seconds': 2., 'window': 'hamming', 'overlap_fraction': .25,
                  'n_fft': 256, 'detrend': 'constant', 'average': 'mean'},
        'numeric_tolerance': {'psd': {'rtol': 1e-10, 'atol': 1e-28},
                              'frequency_atol_hz': 1e-10}}


def test_continuous_runner_refuses_existing_output_before_processing(raw, tmp_path):
    (tmp_path / 'result.json').write_text('first delivery')
    with pytest.raises(FileExistsError):
        run_plan(welch_plan(), raw, tmp_path)
    assert (tmp_path / 'result.json').read_text() == 'first delivery'


def test_later_branch_failure_preserves_first_band_and_marks_run_failed(raw, tmp_path):
    original = raw.get_data().copy()
    plan = {'analysis_channels': raw.ch_names,
        'hilbert_bands': {
            'first': {'operations': [], 'metric': 'plv', 'matrix_key': 'first_matrix'},
            'second': {'operations': [], 'metric': 'unsupported', 'matrix_key': 'second_matrix'}},
        'required_results': {}, 'required_evidence': {}, 'numeric_tolerance': {}}
    with pytest.raises(ValueError, match='approved procedure'):
        run_plan(plan, raw, tmp_path)
    assert json.loads((tmp_path / 'result.json').read_text())['status'] == 'incomplete'
    phase = hilbert(original, axis=-1)
    phase = phase / np.abs(phase)
    expected = abs(phase @ phase.conj().T / phase.shape[-1])
    with np.load(tmp_path / 'analysis_evidence.npz', allow_pickle=False) as arrays:
        np.testing.assert_allclose(arrays['first_matrix'], expected)
        assert 'second_matrix' not in arrays.files
    execution = json.loads((tmp_path / 'execution.json').read_text())
    assert execution['status'] == 'failed'
    assert execution['steps'][-1]['name'] == 'compute:second'
    assert execution['error']['type'] == 'ValueError'
    assert not (tmp_path / 'FINAL_SUBMISSION.md').exists()
    np.testing.assert_array_equal(raw.get_data(), original)


def test_saved_actual_source_and_plan_replay_in_new_directory(raw, tmp_path):
    source = tmp_path / 'input_raw.fif'
    raw.save(source, overwrite=False, verbose=False)
    first, second = tmp_path / 'first', tmp_path / 'replay'
    with mne.io.read_raw_fif(source, preload=False, verbose=False) as loaded:
        result, check = run_plan(welch_plan(), loaded, first)
    assert check['passed']
    record = json.loads((first / 'execution.json').read_text())
    assert record['status'] == 'completed'
    assert record['input_metadata']['channels'] == ['Cz', 'Pz']
    for relative in record['source_files']:
        assert (first / 'executed-source' / relative).read_bytes() == (ROOT / relative).read_bytes()
    repeated = subprocess.run([sys.executable, '-B',
        str(first / 'executed-source/tools/run_continuous_plan.py'),
        '--plan', str(first / 'APPROVED_PLAN.json'), '--input', str(source), '--output', str(second)],
        capture_output=True, text=True)
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads((second / 'result.json').read_text()) == result
    with np.load(first / 'analysis_evidence.npz') as a, np.load(second / 'analysis_evidence.npz') as b:
        assert a.files == b.files
        for key in a.files:
            np.testing.assert_array_equal(a[key], b[key])
