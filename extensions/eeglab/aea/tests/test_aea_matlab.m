% Actual EEGLAB/native arithmetic test. No Python bridge, model or API calls.
function test_aea_matlab(repository, eeglab_path, output)
had_preferences = ispref('AEA'); previous = struct();
if had_preferences, previous = getpref('AEA'); end
cleanup = onCleanup(@() restore_preferences(had_preferences, previous));
addpath(eeglab_path);
addpath(genpath(fullfile(eeglab_path, 'functions')));
addpath(fullfile(eeglab_path, 'plugins', 'dipfit'));
addpath(fullfile(repository, 'extensions', 'eeglab', 'aea'));
EEG = eeg_emptyset();
EEG.nbchan = 2; EEG.pnts = 101; EEG.trials = 4; EEG.srate = 100;
EEG.xmin = -.2; EEG.xmax = .8;
EEG.chanlocs(1).labels = 'Cz'; EEG.chanlocs(2).labels = 'Pz';
EEG.data = zeros(2, 101, 4);
pulses = [1 5 3 7; 2 6 4 8];
for k = 1:4
    EEG.data(:, 21:71, k) = repmat(pulses(:, k), 1, 51);
    type = 'A'; if mod(k, 2) == 0, type = 'B'; end
    EEG.event(k).type = type;
    EEG.event(k).latency = 21+(k-1)*101;
    EEG.event(k).epoch = k;
    EEG.epoch(k).event = k;
    EEG.epoch(k).eventtype = {type};
    EEG.epoch(k).eventlatency = {0};
end
EEG.history = '% Fixed synthetic engineering fixture; no participants or preprocessing';
before = EEG;
project = fullfile(output, 'researcher''s native study');
after = pop_aea(EEG, 'project', project, 'repository', repository, 'backend', 'matlab', ...
    'python', '', 'client', 'codex', 'client_executable', 'codex', 'recipe', 'custom');
assert(isequaln(before, after));
header = jsondecode(fileread(fullfile(project, 'EEGLAB_IMPORT_CHECK.json')));
assert(strcmp(header.backend, 'matlab') && strcmp(header.sample_unit, 'uV'));
environment = jsondecode(fileread(fullfile(project, 'ENVIRONMENT.json')));
assert(~environment.python_required && ~environment.model_invoked);
plan = fullfile(project, 'ANALYSIS_PLAN.md');
fid = fopen(plan, 'w'); fprintf(fid, 'Existing approved synthetic test plan\n'); fclose(fid);
brief = fileread(fullfile(project, 'DATASET_BRIEF.md'));
aea_prepare_matlab(project);
assert(strcmp(fileread(plan), sprintf('Existing approved synthetic test plan\n')));
assert(strcmp(fileread(fullfile(project, 'DATASET_BRIEF.md')), brief));
[command, workspace] = aea_client_command(project);
assert(strcmp(workspace, repository));
assert(~isempty(strfind(command, '--cd')) && ~isempty(strfind(command, '--add-dir')));
assert(isempty(strfind(command, '--model')) && isempty(strfind(command, 'skip-permissions')));
config_path = fullfile(project, 'AEA_BRIDGE_CONFIG.json');
config = jsondecode(fileread(config_path));
config.client = 'claude'; config.client_executable = 'claude';
aea_write_json(config_path, config);
aea_prepare_matlab(project);
command = aea_client_command(project);
assert(~isempty(strfind(command, 'claude')) && isempty(strfind(command, '--cd')));
assert(~isempty(strfind(command, 'AEA_REQUEST.md')));

input_set = fullfile(project, 'input', 'imported.set');
source = read_bytes(input_set);
source_fdt = read_bytes(fullfile(project, 'input', 'imported.fdt'));
spec = struct('roi', {{'Cz', 'Pz'}}, 'window_s', [.1 .3], ...
    'condition_names', {{'A', 'B'}}, 'condition_epochs', {{[1 3], [2 4]}}, 'contrast', [2 1]);
first = fullfile(project, 'first-delivery');
results = aea_erp_mean(input_set, first, spec);
assert(max(abs(results.condition_means_uV - [2.5 6.5])) < 1e-6);
assert(abs(results.contrast_uV - 4) < 1e-6);
assert(isequal(results.sample_indices_one_based, 31:51));
assert(isequal(results.epoch_counts, [2 2]));
assert(isequal(source, read_bytes(input_set)));
assert(isequal(source_fdt, read_bytes(fullfile(project, 'input', 'imported.fdt'))));
addpath(first);
replayed = run_analysis(fullfile(project, 'replay'));
assert(isequal(results, replayed));
% Different list lengths verify equal per-epoch weighting and executable replay.
spec.condition_epochs = {[1], [2 3 4]};
unequal_dir = fullfile(project, 'unequal');
unequal = aea_erp_mean(input_set, unequal_dir, spec);
assert(max(abs(unequal.condition_means_uV - [1.5 5.5])) < 1e-6);
rmpath(first); addpath(unequal_dir); clear run_analysis;
unequal_replay = run_analysis(fullfile(project, 'unequal-replay'));
assert(isequal(unequal, unequal_replay));
spec.roi = {'missing'};
failed = false;
try
    aea_erp_mean(input_set, fullfile(project, 'invalid-roi'), spec);
catch failure
    failed = strcmp(failure.identifier, 'AEA:ROI');
end
assert(failed && ~exist(fullfile(project, 'invalid-roi'), 'dir'));
fprintf('AEA_MATLAB_NATIVE_TEST_PASSED\n');
end

function bytes = read_bytes(path)
fid = fopen(path, 'rb');
cleanup = onCleanup(@() fclose(fid));
bytes = fread(fid, Inf, '*uint8');
end

function restore_preferences(had_preferences, previous)
if ispref('AEA'), rmpref('AEA'); end
if had_preferences
    names = fieldnames(previous);
    for k = 1:numel(names), setpref('AEA', names{k}, previous.(names{k})); end
end
end
