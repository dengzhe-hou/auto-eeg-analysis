% Run against real EEGLAB functions; no signal-processing or model stubs.
function test_aea_export(repository, eeglab, output, python)
had_preferences = ispref('AEA');
previous_preferences = struct();
if had_preferences, previous_preferences = getpref('AEA'); end
pref_cleanup = onCleanup(@() restore_preferences(had_preferences, previous_preferences));
addpath(genpath(fullfile(eeglab, 'functions')));
addpath(fullfile(eeglab, 'plugins', 'dipfit'));
addpath(fullfile(repository, 'extensions', 'eeglab', 'aea'));

EEG = eeg_emptyset();
EEG.nbchan = 2; EEG.pnts = 1000; EEG.trials = 1; EEG.srate = 100;
EEG.data = [10*sin((0:999)*.1); 20*cos((0:999)*.1)];
EEG.xmin = 0; EEG.xmax = 9.99;
EEG.chanlocs(1).labels = 'Cz'; EEG.chanlocs(2).labels = 'Pz';
EEG.event = struct('type', {'a', 'b'}, 'latency', {101,301}, 'duration', {0,0});
EEG.history = '% Synthetic adapter test; no processing applied';
before = EEG;
project = fullfile(output, 'researcher''s continuous study');
[after, com] = pop_aea(EEG, 'project', project, 'repository', repository, ...
    'python', python, 'client', 'codex', 'recipe', 'custom');
assert(isequaln(before, after));
assert(~isempty(strfind(com, 'pop_aea')));
assert(exist(fullfile(project, 'AEA_HANDOFF.json'), 'file') == 2);
failed = false;
try
    aea_export(EEG, project);
catch error_info
    failed = strcmp(error_info.identifier, 'AEA:ExistingExport');
end
assert(failed);

EEG = eeg_emptyset();
EEG.nbchan = 2; EEG.pnts = 101; EEG.trials = 4; EEG.srate = 100;
EEG.xmin = -.2; EEG.xmax = .8;
EEG.chanlocs(1).labels = 'Cz'; EEG.chanlocs(2).labels = 'Pz';
EEG.data = zeros(2,101,4);
for k = 1:4
    EEG.data(:,:,k) = [(0:100)+k; -(0:100)-k];
    type = 'a'; if mod(k, 2) == 0, type = 'b'; end
    EEG.event(k).type = type;
    EEG.event(k).latency = 21+(k-1)*101;
    EEG.event(k).epoch = k;
    EEG.epoch(k).event = k;
    EEG.epoch(k).eventtype = {type};
    EEG.epoch(k).eventlatency = {0};
end
project = fullfile(output, 'epoched study');
before = EEG;
after = pop_aea(EEG, 'project', project, 'repository', repository, ...
    'python', python, 'client', 'claude', 'recipe', 'custom');
assert(isequaln(before, after));
assert(exist(fullfile(project, 'AEA_HANDOFF.json'), 'file') == 2);

% Check menu objects and the public callback, without pretending a MATLAB GUI
% was tested on this headless Octave installation.
if ~isempty(available_graphics_toolkits())
    fig = figure('visible', 'off');
    cleanup = onCleanup(@() close(fig));
    uimenu(fig, 'Tag', 'tools', 'Label', 'Tools');
    version = eegplugin_aea(fig, struct('no_check', ''), struct('add_to_hist', ''));
    assert(strcmp(version, 'aea0.1.0'));
    menu = findobj(fig, 'Tag', 'aea_export');
    assert(numel(menu) == 1);
    assert(~isempty(strfind(get(menu, 'Callback'), 'pop_aea')));
end
fprintf('AEA_EXPORT_TEST_PASSED\n');
end

function restore_preferences(had_preferences, previous)
if ispref('AEA'), rmpref('AEA'); end
if had_preferences
    names = fieldnames(previous);
    for k = 1:numel(names), setpref('AEA', names{k}, previous.(names{k})); end
end
end
