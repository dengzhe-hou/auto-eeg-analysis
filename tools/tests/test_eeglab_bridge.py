"""Exercise the EEGLAB handoff with real .set imports and optional Octave/EEGLAB.

These checks never invoke a live coding assistant or paid API.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
from zipfile import ZipFile

import mne
import numpy as np
import pytest
from scipy.io import savemat

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import eeglab_bridge as bridge
from package_eeglab_plugin import build_archive


@pytest.fixture
def study(tmp_path):
    repository = tmp_path / 'AEA checkout'
    repository.mkdir()
    (repository / 'AGENT_GUIDE.md').write_text('Use approved choices.\n', encoding='utf-8')
    skill = repository / 'skills/eeg-recipe'
    skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text('Recipe routing\n', encoding='utf-8')
    recipe = repository / 'recipes/n400-semantic'
    recipe.mkdir(parents=True)
    (recipe / 'RECIPE.md').write_text('Example recipe\n', encoding='utf-8')
    project = tmp_path / "researcher's EEG study"
    (project / 'input').mkdir(parents=True)
    values = np.array([np.sin(np.arange(500) * .2) * 10,
                       np.cos(np.arange(500) * .2) * 20], dtype=np.float32)
    savemat(project / 'input/imported.set', {'EEG': {
        'data': values, 'srate': 100., 'nbchan': 2, 'pnts': 500, 'trials': 1,
        'xmin': 0., 'xmax': 4.99, 'chanlocs': [{'labels': 'Cz'}, {'labels': 'Pz'}],
        'event': [{'type': 'stimulus', 'latency': 101., 'duration': 0.}],
    }})
    bridge.write_json(project / 'EEGLAB_EXPORT.json', {
        'dataset_kind': 'continuous', 'input_file': 'input/imported.set',
        'n_channels': 2, 'n_samples_per_epoch': 500, 'n_epochs': 1,
        'srate': 100., 'epoch_tmin_s': 0.,
    })
    bridge.write_json(project / 'AEA_BRIDGE_CONFIG.json', {
        'repository': str(repository), 'python': sys.executable,
        'client': 'codex', 'recipe': 'n400-semantic',
    })
    return project, repository, values


def test_prepare_reads_real_set_and_does_not_start_a_model(study, monkeypatch):
    project, repository, values = study

    original_popen = bridge.subprocess.Popen

    def reject_assistant(command, *args, **kwargs):
        executable = Path(command[0]).name.lower()
        if executable in {'codex', 'claude', 'codex.exe', 'claude.exe', 'codex.cmd', 'claude.cmd'}:
            pytest.fail('Preparation must not launch a coding assistant')
        # MNE/Matplotlib may query fonts with fc-list on a cold machine.
        return original_popen(command, *args, **kwargs)

    def reject_session(*args, **kwargs):
        pytest.fail('Preparation must not start an assistant session')

    monkeypatch.setattr(bridge.subprocess, 'Popen', reject_assistant)
    monkeypatch.setattr(bridge, 'session', reject_session)
    monkeypatch.setattr(bridge, 'launch', reject_session)
    result = bridge.prepare(project)
    assert result['status'] == 'prepared'
    raw = mne.io.read_raw_eeglab(project / 'input/imported.set', preload=True, verbose='ERROR')
    np.testing.assert_allclose(raw.get_data(), values * 1e-6, atol=1e-12)
    header = bridge.read_json(project / 'EEGLAB_IMPORT_CHECK.json')
    assert header['n_channels'] == 2 and header['n_epochs'] == 1
    handoff = bridge.read_json(project / 'AEA_HANDOFF.json')
    assert handoff['scientific_plan_approved_by_export'] is False
    assert handoff['model_invoked_during_preparation'] is False
    assert (repository / '.agents/skills/eeg-recipe').resolve() == repository / 'skills/eeg-recipe'
    assert (project / 'DATASET_BRIEF.md').exists()


def test_existing_brief_and_approved_plan_are_preserved(study):
    project, _, _ = study
    for name in ['DATASET_BRIEF.md', 'ANALYSIS_PLAN.md']:
        (project / name).write_text('Researcher-owned settings\n', encoding='utf-8')
    bridge.prepare(project)
    for name in ['DATASET_BRIEF.md', 'ANALYSIS_PLAN.md']:
        assert (project / name).read_text(encoding='utf-8-sig') == 'Researcher-owned settings\n'


def test_import_mismatch_is_rejected(study):
    project, _, _ = study
    path = project / 'EEGLAB_EXPORT.json'
    data = bridge.read_json(path)
    data['n_channels'] = 3
    bridge.write_json(path, data)
    with pytest.raises(ValueError, match='dimensions/rate differ'):
        bridge.prepare(project)
    assert not (project / 'AEA_HANDOFF.json').exists()


@pytest.mark.parametrize('client', ['codex', 'claude'])
def test_session_routes_workspace_and_keeps_client_configuration(study, monkeypatch, client):
    project, repository, _ = study
    bridge.prepare(project)
    path = project / 'AEA_BRIDGE_CONFIG.json'
    config = bridge.read_json(path)
    config['client'] = client
    config['client_executable'] = sys.executable  # no assistant is actually run
    bridge.write_json(path, config)
    captured = {}

    def call(command, *, cwd, env):
        captured.update(command=command, cwd=cwd, env=env)
        return 7

    monkeypatch.setattr(bridge.subprocess, 'call', call)
    assert bridge.session(project) == 7
    assert captured['cwd'] == repository
    assert str(project) in captured['command']
    assert str(project / 'AEA_REQUEST.md') in captured['command'][-1]
    assert '--model' not in captured['command']
    assert not any('bypass' in arg or 'skip-permissions' in arg for arg in captured['command'])
    assert captured['env']['PATH'].split(os.pathsep)[0] == str(Path(sys.executable).parent)


def test_headless_launch_reports_a_manual_command(study, monkeypatch):
    project, _, _ = study
    bridge.prepare(project)
    config_path = project / 'AEA_BRIDGE_CONFIG.json'
    config = bridge.read_json(config_path)
    config['client_executable'] = sys.executable
    bridge.write_json(config_path, config)
    monkeypatch.setattr(bridge.sys, 'platform', 'linux')
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.delenv('WAYLAND_DISPLAY', raising=False)
    with pytest.raises(RuntimeError, match='Run this in your terminal instead'):
        bridge.launch(project)


def test_plugin_archive_contains_the_installable_entrypoint_and_license(tmp_path):
    archive = build_archive(ROOT, tmp_path / 'aea-eeglab.zip')
    with ZipFile(archive) as package:
        names = package.namelist()
        assert 'aea0.1.1/eegplugin_aea.m' in names
        assert 'aea0.1.1/pop_aea.m' in names
        assert 'aea0.1.1/README.md' in names
        assert 'aea0.1.1/LICENSE' in names
        assert not any(name.endswith(('.set', '.fdt', '.json')) for name in names)


def test_actual_octave_eeglab_export_roundtrip(tmp_path):
    octave = os.environ.get('AEA_OCTAVE') or shutil.which('octave-cli')
    eeglab = Path(os.environ.get('EEGLAB_PATH', str(Path.home() / 'eeglab')))
    if not octave or not (eeglab / 'eeglab.m').is_file():
        pytest.skip('Set AEA_OCTAVE and EEGLAB_PATH for the actual Octave/EEGLAB integration test')
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    script = tmp_path / 'test_export.m'
    script.write_text(
        f"addpath({quote(ROOT / 'extensions/eeglab/aea/tests')});\n"
        f"test_aea_export({quote(ROOT)}, {quote(eeglab)}, {quote(tmp_path)}, {quote(sys.executable)});\n",
        encoding='utf-8')
    env = os.environ.copy()
    env['OCTAVE_HOME'] = str(Path(octave).resolve().parents[1])
    result = subprocess.run([octave, '--no-gui', '--quiet', str(script)], env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ["researcher's continuous study", 'epoched study']:
        project = tmp_path / name
        header = bridge.read_json(project / 'EEGLAB_IMPORT_CHECK.json')
        assert header['n_channels'] == 2
        if header['dataset_kind'] == 'continuous':
            raw = mne.io.read_raw_eeglab(project / 'input/imported.set', preload=True, verbose='ERROR')
            expected = np.vstack([10 * np.sin(np.arange(1000) * .1),
                                  20 * np.cos(np.arange(1000) * .1)]) * 1e-6
            np.testing.assert_allclose(raw.get_data(), expected, rtol=1e-6, atol=1e-12)
            np.testing.assert_allclose(raw.annotations.onset, [1., 3.])
            events = bridge.read_json(project / 'input/events.json')
            assert [event['latency'] for event in events['events']] == [101, 301]
        else:
            epochs = mne.read_epochs_eeglab(project / 'input/imported.set', verbose='ERROR')
            assert len(epochs) == 4
            np.testing.assert_allclose(epochs.times[[0, -1]], [-.2, .8])
            assert set(epochs.event_id) == {'a', 'b'}
            expected = np.stack([np.vstack([np.arange(101)+i, -np.arange(101)-i])
                                 for i in range(1, 5)]) * 1e-6
            np.testing.assert_allclose(epochs.get_data(), expected, atol=1e-12)
