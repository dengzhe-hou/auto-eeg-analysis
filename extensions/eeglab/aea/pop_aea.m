% POP_AEA - Prepare an AEA study from EEGLAB, start the client or open a report.
%
% [EEG, com, info] = pop_aea(EEG)                % export dialog
% pop_aea([], 'action', 'configure')            % first-time settings
% pop_aea([], 'action', 'launch', 'project', folder)
% pop_aea([], 'action', 'report', 'project', folder)
%
% Noninteractive export uses project, repository, client, and optional backend,
% python, recipe/client_executable arguments. MATLAB backend needs no Python.
% Export does not run a model or analysis.
function [EEG, com, info] = pop_aea(EEG, varargin)
com = ''; info = struct();
p = inputParser;
addParameter(p, 'action', 'export');
addParameter(p, 'project', '');
addParameter(p, 'repository', pref('repository', ''));
addParameter(p, 'python', pref('python', ''));
addParameter(p, 'client', pref('client', ''));
addParameter(p, 'client_executable', pref('client_executable', ''));
addParameter(p, 'backend', pref('backend', 'mne'));
addParameter(p, 'recipe', 'custom');
parse(p, varargin{:});
o = p.Results;
if strcmp(o.action, 'configure')
    values = inputdlg({'AEA checkout folder', 'Python executable in the AEA environment', ...
        'Coding assistant (codex or claude)', 'Assistant executable (name or full path)', ...
        'Analysis backend (mne or matlab; Python is optional for matlab)'}, ...
        'AEA settings', [1 75], {o.repository, o.python, o.client, o.client_executable, o.backend});
    if isempty(values), return; end
    o.repository = values{1}; o.python = values{2};
    o.client = values{3}; o.client_executable = values{4};
    o.backend = values{5};
    validate_settings(o);
    setpref('AEA', 'repository', o.repository); setpref('AEA', 'python', o.python);
    setpref('AEA', 'client', o.client); setpref('AEA', 'client_executable', o.client_executable);
    setpref('AEA', 'backend', o.backend);
    info = o;
    return;
end
if ~any(strcmp(o.action, {'export', 'launch', 'report'}))
    error('AEA:Action', 'Unknown AEA action: %s', o.action);
end
if isempty(o.project)
    o.project = uigetdir(pref('project', pwd), 'Choose the study folder (new folder for export)');
    if isequal(o.project, 0), return; end
    if strcmp(o.action, 'export')
        validate_settings(o);
        items = dir(fullfile(o.repository, 'recipes'));
        recipes = {'custom'};
        for i = 1:numel(items)
            if items(i).isdir && exist(fullfile(o.repository, 'recipes', items(i).name, 'RECIPE.md'), 'file') && items(i).name(1) ~= '_'
                recipes{end+1} = items(i).name;
            end
        end
        [choice, okay] = listdlg('PromptString', 'Choose a recipe, or custom to discuss the study in AEA', ...
            'SelectionMode', 'single', 'ListString', recipes);
        if ~okay, return; end
        o.recipe = recipes{choice};
    end
end
if strcmp(o.action, 'report')
    report = fullfile(o.project, 'report-stage', 'report.html');
    if ~exist(report, 'file')
        error('AEA:NoReport', 'No report-stage/report.html yet. Complete the analysis in AEA, then open the report.');
    end
    web(report, '-browser');
    info.report = report;
    return;
end
if strcmp(o.action, 'launch')
    config = jsondecode(fileread(fullfile(o.project, 'AEA_BRIDGE_CONFIG.json')));
    o.repository = config.repository; o.python = config.python;
    o.client = config.client;
    o.backend = 'mne';
    if isfield(config, 'backend'), o.backend = config.backend; end
end
validate_settings(o);
bridge = fullfile(o.repository, 'tools', 'eeglab_bridge.py');
if strcmp(o.action, 'export')
    info = aea_export(EEG, o.project);
    config = struct('repository', o.repository, 'python', o.python, ...
        'client', o.client, 'client_executable', o.client_executable, 'recipe', o.recipe, ...
        'backend', o.backend);
    aea_write_json(fullfile(o.project, 'AEA_BRIDGE_CONFIG.json'), config);
    if strcmp(o.backend, 'matlab')
        aea_prepare_matlab(o.project);
    else
        run_bridge(o.python, bridge, 'prepare', o.project);
    end
    if ~exist(fullfile(o.project, 'AEA_HANDOFF.json'), 'file')
        error('AEA:PreparationFailed', 'The dataset was exported, but preparation did not complete. Check the backend error and retry preparation.');
    end
    com = sprintf('[EEG, LASTCOM] = pop_aea(EEG, ''action'', ''export'', ''project'', %s, ''repository'', %s, ''python'', %s, ''client'', %s, ''client_executable'', %s, ''recipe'', %s, ''backend'', %s);', ...
        literal(o.project), literal(o.repository), literal(o.python), literal(o.client), literal(o.client_executable), literal(o.recipe), literal(o.backend));
    fprintf('AEA study prepared: %s\nStart AEA from Tools > AEA when ready to discuss the plan.\n', o.project);
else
    if strcmp(o.backend, 'matlab')
        info = aea_launch_matlab(o.project);
    else
        run_bridge(o.python, bridge, 'launch', o.project);
    end
end
setpref('AEA', 'project', o.project);
end

function value = pref(name, fallback)
value = fallback;
if ispref('AEA', name), value = getpref('AEA', name); end
end

function validate_settings(o)
if ~exist(fullfile(o.repository, 'AGENT_GUIDE.md'), 'file')
    error('AEA:Repository', 'Select an AEA checkout containing AGENT_GUIDE.md in Tools > AEA > Settings.');
end
if ~any(strcmp(o.backend, {'mne', 'matlab'}))
    error('AEA:Backend', 'Choose mne or matlab in AEA settings.');
end
if strcmp(o.backend, 'mne') && (isempty(o.python) || ~exist(o.python, 'file'))
    error('AEA:Python', 'Select the Python executable in your AEA environment.');
end
if ~any(strcmp(o.client, {'codex', 'claude'}))
    error('AEA:Client', 'Choose codex or claude in AEA settings.');
end
end

function run_bridge(python, bridge, action, project)
cmd = [aea_shell_quote(python) ' ' aea_shell_quote(bridge) ' ' action ...
    ' --project ' aea_shell_quote(project) ' 2>&1'];
[status, output] = system(cmd);
if status ~= 0, error('AEA:Bridge', '%s', output); end
jsondecode(output); % A successful bridge action returns its JSON completion receipt.
fprintf('%s', output);
end

function text = literal(value)
text = [char(39) strrep(value, char(39), [char(39) char(39)]) char(39)];
end
