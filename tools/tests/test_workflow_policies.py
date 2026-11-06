"""Approved ICA decisions, actual uncertainty artists, and run-control selection."""
from pathlib import Path
from types import SimpleNamespace
import json
import re
import runpy
import subprocess
import sys
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import mne
import numpy as np
import pytest
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from load_skill import read_section
from run_settings import load_run_settings, select_reviewer
choose = runpy.run_path(str(ROOT / 'skills/eeg-ica/scripts/selection.py'))['choose_components']
mean_band = runpy.run_path(str(ROOT / 'skills/eeg-figure/scripts/variability.py'))['mean_band']


def selection(labels, probabilities, corroboration, **overrides):
    policy = dict(reject_classes=['eye blink','heart beat','muscle artifact'],
                  probability_threshold=.7, require_corroboration=True)
    return choose(labels, probabilities, corroborating_components=corroboration, **{**policy, **overrides})


@pytest.mark.parametrize('evidence,reason', [(None,'corroboration_unavailable'), ([], 'not_corroborated')])
def test_high_probability_does_not_replace_required_evidence(evidence, reason):
    out = selection(['eye blink'], [.99], {'eye blink': evidence})
    assert out['excluded'] == [] and out['ambiguous'] == [0]
    assert out['decisions'][0]['reason'] == reason


def test_corroboration_must_match_both_class_and_component():
    out = selection(['eye blink','heart beat','muscle artifact'], [.99,.8,.7],
                    {'eye blink':[1], 'heart beat':[1], 'muscle artifact':[2]})
    assert out['excluded'] == [1,2] and out['ambiguous'] == [0]
    assert selection(['eye blink'], [.69], {'eye blink':[0]})['ambiguous'] == [0]


def test_protected_and_unauthorized_classes_are_not_auto_excluded():
    out = selection(['brain','other','line noise','eye blink'], [.99]*4,
        {'brain':[0],'other':[1],'line noise':[2],'eye blink':[3]},
        reject_classes=['brain','other','eye blink'])
    assert out['retained'] == [0,2] and out['ambiguous'] == [1] and out['excluded'] == [3]


def test_no_corroboration_policy_is_only_used_when_explicitly_supplied():
    assert selection(['eye blink'], [.99], {}, require_corroboration=False)['excluded'] == [0]
    with pytest.raises(TypeError, match='require_corroboration'):
        choose(['eye blink'], [.99], reject_classes=['eye blink'], probability_threshold=.7,
               corroborating_components={})
    with pytest.raises(ValueError, match='one finite'):
        selection(['eye blink'], [[.99, .01]], {})


def test_actual_ica_decision_example_uses_the_policy_and_class_evidence():
    text = (ROOT / 'skills/eeg-ica/references/procedure.md').read_text()
    code = textwrap.dedent(next(b for b in re.findall(r'```python\n(.*?)```',text,re.S)
                               if 'selection = choose' in b))
    policy = dict(reject_classes=['eye blink'], probability_threshold=.7, require_corroboration=True)
    namespace = {'AEA_ROOT':ROOT, 'ica':SimpleNamespace(exclude=[]),
        'approved_ica_params':{'rejection_policy':policy},
        'ic_labels':{'labels':['eye blink'],'y_pred_proba':np.array([.99])},
        'eog_idx':[], 'ecg_idx':[0], 'muscle_idx':[0]}
    exec(compile(code,'documented ICA selection','exec'),namespace)
    assert namespace['ica'].exclude == [] and namespace['ambiguous'] == [0]
    namespace['eog_idx'] = [0]
    exec(compile(code,'documented ICA selection','exec'),namespace)
    assert namespace['ica'].exclude == [0] and namespace['ambiguous'] == []


@pytest.mark.parametrize('ddof', [0,1])
def test_sem_preserves_the_explicit_sd_convention(ddof):
    data = np.repeat(np.array([1.,2.,4.,6.,10.])[:,None], 20, axis=1)
    spec = {'kind':'sem','std_ddof':ddof,'unit':'uV','observation_unit':'participants'}
    out = mean_band(data, specification=spec)
    expected = np.std(data[:,0], ddof=ddof)/np.sqrt(5)
    np.testing.assert_allclose(out['mean']-out['lower'], expected)
    assert f'ddof={ddof}' in out['caption'] and 'N=5 participants' in out['caption']
    assert '95%' not in out['caption']


def test_student_interval_has_the_correct_finite_sample_width():
    data = np.repeat(np.array([1.,2.,4.,6.,10.])[:,None], 20, axis=1)
    spec = {'kind':'student_t_ci','std_ddof':1,'level':.95,'sidedness':'two-sided','unit':'uV','observation_unit':'participants'}
    out = mean_band(data, specification=spec)
    expected = t.ppf(.975,4)*np.std(data[:,0],ddof=1)/np.sqrt(5)
    np.testing.assert_allclose(out['upper']-out['mean'], expected)
    assert '95% Student-t CI (df=4)' in out['caption']
    with pytest.raises(ValueError, match='sample SD'):
        mean_band(data,specification={**spec,'std_ddof':0})
    with pytest.raises(ValueError, match='two-sided'):
        mean_band(data,specification={**spec,'sidedness':'one-sided'})


def test_bootstrap_preserves_seed_and_method_in_numbers_and_caption():
    data = np.repeat(np.array([1.,2.,4.,6.,10.])[:,None], 20, axis=1)
    spec = {'kind':'bootstrap_ci','method':'percentile','level':.95,'sidedness':'two-sided','n_resamples':400,
            'seed':31,'unit':'uV','observation_unit':'participants'}
    a=mean_band(data,specification=spec); b=mean_band(data,specification=spec)
    np.testing.assert_array_equal(a['lower'],b['lower'])
    np.testing.assert_array_equal(a['upper'],b['upper'])
    scaled=mean_band(data*1e-6,specification={**spec,'unit':'V'})
    np.testing.assert_allclose(scaled['lower']*1e6,a['lower'])
    assert '95% percentile-bootstrap CI' in a['caption'] and '400 resamples; seed=31' in a['caption']
    with pytest.raises(KeyError,match='seed'):
        mean_band(data,specification={k:v for k,v in spec.items() if k!='seed'})


@pytest.mark.parametrize('spec', [
    {'kind':'sem','std_ddof':1},
    {'kind':'student_t_ci','std_ddof':1,'level':.95,'sidedness':'two-sided'},
    {'kind':'bootstrap_ci','method':'percentile','level':.95,'sidedness':'two-sided','n_resamples':400,'seed':31}])
def test_actual_group_erp_example_and_mne_callback_draw_the_captioned_bounds(spec):
    spec={**spec,'unit':'uV','observation_unit':'participants'}
    observations=np.array([1.,2.,4.,6.,10.])
    info=mne.create_info(['Cz','Pz'],100.,'eeg')
    evokeds=[mne.EvokedArray(np.full((2,20),v*1e-6),info,tmin=-.1,verbose=False) for v in observations]
    text=(ROOT/'skills/eeg-figure/references/procedure.md').read_text()
    section=read_section(text,'Group ERP with the approved uncertainty band')
    blocks=re.findall(r'```python\n(.*?)```',section,re.S)
    fig,ax=plt.subplots()
    namespace={'AEA_ROOT':ROOT,'mne':mne,'evokeds_A':evokeds,'roi_channels':['Cz','Pz'],
               'approved_band_spec':spec,'ax':ax}
    exec(compile(blocks[0],'documented manual ERP band','exec'),namespace)
    expected=namespace['band']
    polygon=next(c for c in ax.collections if isinstance(c,PolyCollection)).get_paths()[0].vertices
    np.testing.assert_allclose([polygon[:,1].min(),polygon[:,1].max()],
                               [expected['lower'][0],expected['upper'][0]])
    assert namespace['band_caption']==expected['caption']
    exec(compile(blocks[1],'documented MNE interval callback','exec'),namespace)
    callback_polygon=next(c for c in namespace['figures'][0].axes[0].collections
                          if isinstance(c,PolyCollection)).get_paths()[0].vertices
    np.testing.assert_allclose([callback_polygon[:,1].min(),callback_polygon[:,1].max()],
                               [expected['lower'][0],expected['upper'][0]])
    assert namespace['captions']==[expected['caption']]
    plt.close('all')


def test_uncertainty_method_and_missing_choices_do_not_get_silent_defaults():
    data=np.ones((3,5))
    with pytest.raises(KeyError,match='kind'):
        mean_band(data,specification={})
    with pytest.raises(ValueError,match='own implementation'):
        mean_band(data,specification={'kind':'unknown','unit':'V','observation_unit':'participants'})


@pytest.fixture
def isolated_config(tmp_path,monkeypatch):
    fake_home=tmp_path/'fake-home'; fake_home.mkdir()
    monkeypatch.setattr(Path,'home',lambda:fake_home)
    project=tmp_path/'my study'; project.mkdir()
    return project,fake_home


def test_configuration_source_priority_preserves_actual_controls(isolated_config,tmp_path):
    project,fake_home=isolated_config
    default=load_run_settings(project)
    assert default['source'] is None and default['auto_proceed'] is True and default['timeout_seconds']==300
    legacy=fake_home/'.claude/checkpoint.json'; legacy.parent.mkdir()
    legacy.write_text(json.dumps({'auto_proceed':False,'timeout_seconds':19,'gates':{'ica':'always_wait'}}))
    out=load_run_settings(project)
    assert out['source']==str(legacy) and out['gates']=={'ica':'always_wait'}
    own=project/'AEA_RUN.json'; own.write_text(json.dumps({'auto_proceed':True,'timeout_seconds':51}))
    assert load_run_settings(project)['source']==str(own)
    explicit=tmp_path/'chosen.json'; explicit.write_text(json.dumps({'auto_proceed':False,'timeout_seconds':73}))
    out=load_run_settings(project,config_path=explicit)
    assert out['source']==str(explicit) and out['timeout_seconds']==73 and out['auto_proceed'] is False
    with pytest.raises(FileNotFoundError):
        load_run_settings(project,config_path=tmp_path/'missing.json')


def test_settings_cli_reads_the_named_project_file(isolated_config):
    project,_=isolated_config
    config=project/'AEA_RUN.json'; config.write_text(json.dumps({'auto_proceed':False,'timeout_seconds':41}))
    run=subprocess.run([sys.executable,str(ROOT/'tools/run_settings.py'),'--project',str(project),
                        '--config',str(config)],check=True,capture_output=True,text=True)
    result=json.loads(run.stdout)
    assert result['source']==str(config) and result['timeout_seconds']==41


def test_selected_reviewer_does_not_depend_on_unselected_connections():
    settings={'reviewer':{'transport':'codex-cli','model':'approved-model','effort':'approved-effort'}}
    result=select_reviewer(settings,available_transports=['codex-cli'])
    assert result==settings['reviewer']
    with pytest.raises(RuntimeError,match='incomplete'):
        select_reviewer(settings,available_transports=['llm-chat','codex'])
    with pytest.raises(ValueError,match='approved'):
        select_reviewer({'reviewer':None},available_transports=['codex-cli'])
