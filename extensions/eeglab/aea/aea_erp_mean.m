% AEA_ERP_MEAN - Explicit epoched ERP means, plot and report in MATLAB/EEGLAB.
%
% results = aea_erp_mean(input_set, output_dir, spec)
% spec must provide roi (cell array of labels), window_s ([start end]),
% condition_names, condition_epochs (cell arrays of one-based epoch indices),
% and contrast ([minuend subtrahend] condition indices). No method defaults.
% This bounded helper does not preprocess, reject trials or test significance.
% The researcher approves the study-local plan before calling this function.
function results = aea_erp_mean(input_set, output_dir, spec)
required = {'roi', 'window_s', 'condition_names', 'condition_epochs', 'contrast'};
for i = 1:numel(required)
    if ~isfield(spec, required{i})
        error('AEA:Specification', 'Specify %s in the approved analysis plan.', required{i});
    end
end
spec.roi = reshape(spec.roi, 1, []);
spec.condition_names = reshape(spec.condition_names, 1, []);
spec.condition_epochs = reshape(spec.condition_epochs, 1, []);
[found, input_attributes] = fileattrib(input_set);
if ~found, error('AEA:Input', 'Input SET file not found: %s', input_set); end
input_set = input_attributes.Name;
[folder, name, extension] = fileparts(input_set);
EEG = pop_loadset('filename', [name extension], 'filepath', folder);
if EEG.trials < 2
    error('AEA:EpochedInput', 'This helper requires at least two existing epochs.');
end
[present, channels] = ismember(spec.roi, {EEG.chanlocs.labels});
if isempty(channels) || ~all(present) || numel(unique(channels)) ~= numel(channels)
    error('AEA:ROI', 'Every ROI channel must exist exactly once; no substitution is applied.');
end
window = reshape(spec.window_s, 1, []);
times = EEG.xmin + (0:EEG.pnts-1) / EEG.srate;
epsilon = 1e-9 / EEG.srate;
if numel(window) ~= 2 || any(~isfinite(window)) || window(1) > window(2) || ...
        window(1) < times(1)-epsilon || window(2) > times(end)+epsilon
    error('AEA:Window', 'Specify an ordered, finite time window inside the existing epochs.');
end
samples = find(times >= window(1)-epsilon & times <= window(2)+epsilon);
if isempty(samples), error('AEA:Window', 'The specified window contains no samples.'); end
count = numel(spec.condition_names);
if count < 2 || count ~= numel(spec.condition_epochs) || numel(unique(spec.condition_names)) ~= count
    error('AEA:Conditions', 'Specify distinct condition names and matching epoch-index lists.');
end
contrast = reshape(spec.contrast, 1, []);
if numel(contrast) ~= 2 || any(~isfinite(contrast)) || ...
        any(contrast ~= fix(contrast)) || any(contrast < 1 | contrast > count) || contrast(1) == contrast(2)
    error('AEA:Contrast', 'Specify two distinct condition indices as [minuend subtrahend].');
end
traces = zeros(count, EEG.pnts);
means = zeros(1, count);
epoch_counts = zeros(1, count);
epoch_means = cell(1, count);
for i = 1:count
    epochs = reshape(spec.condition_epochs{i}, 1, []);
    spec.condition_epochs{i} = epochs;
    if isempty(epochs) || any(~isfinite(epochs)) || any(epochs ~= fix(epochs)) || ...
            any(epochs < 1 | epochs > EEG.trials) || numel(unique(epochs)) ~= numel(epochs)
        error('AEA:Epochs', 'Each condition needs unique, existing one-based epoch indices.');
    end
    % EEGLAB stores microvolts. Equal channel and epoch weights; no V conversion.
    channel_mean = mean(double(EEG.data(channels, :, epochs)), 1);
    traces(i, :) = reshape(mean(channel_mean, 3), 1, EEG.pnts);
    epoch_means{i} = reshape(mean(channel_mean(1, samples, :), 2), 1, numel(epochs));
    means(i) = mean(epoch_means{i});
    epoch_counts(i) = numel(epochs);
end
if any(~isfinite(means)) || any(~isfinite(traces(:)))
    error('AEA:NonfiniteData', 'Selected samples contain nonfinite values; no omission rule was approved.');
end
% A fresh output directory preserves first delivery and later replays separately.
if exist(output_dir, 'dir') || exist(output_dir, 'file')
    error('AEA:ExistingOutput', 'Choose a new output directory to preserve previous results.');
end
mkdir(output_dir);
[~, output_attributes] = fileattrib(output_dir);
output_dir = output_attributes.Name;
figures = fullfile(output_dir, 'figure-stage'); mkdir(figures);
report_dir = fullfile(output_dir, 'report-stage'); mkdir(report_dir);
results = struct('backend', 'matlab_eeglab', 'input_file', input_set, 'unit', 'uV', ...
    'roi', {spec.roi}, 'condition_names', {spec.condition_names}, ...
    'condition_epochs', {spec.condition_epochs}, 'epoch_counts', epoch_counts, ...
    'window_s', window, 'sample_indices_one_based', samples, ...
    'sample_times_s', times(samples), 'epoch_means_uV', {epoch_means}, ...
    'condition_means_uV', means, 'contrast', contrast, ...
    'contrast_uV', means(contrast(1))-means(contrast(2)), ...
    'weighting', 'equal channels, equal epochs within each condition', ...
    'processing_applied', 'arithmetic means only; existing epochs retained', ...
    'statistical_inference', false);
aea_write_json(fullfile(output_dir, 'results.json'), results);
aea_write_json(fullfile(output_dir, 'analysis-spec.json'), spec);
aea_write_json(fullfile(output_dir, 'plot_data.json'), struct('time_s', times, ...
    'condition_names', {spec.condition_names}, 'traces_uV', traces));
aea_write_json(fullfile(output_dir, 'ENVIRONMENT.json'), struct('runtime_version', version, ...
    'runtime', computer, 'reader', which('pop_loadset'), 'helper', mfilename('fullpath'), ...
    'python_required', false));

% Same print dimensions and type sizes as AEA's figure rules, in native MATLAB.
fig = figure('Visible', 'off', 'Units', 'centimeters', 'Position', [1 1 8.8 6], ...
    'Color', 'white', 'PaperUnits', 'centimeters', 'PaperSize', [8.8 6], ...
    'PaperPosition', [0 0 8.8 6]);
cleanup = onCleanup(@() close(fig));
ax = axes('Parent', fig, 'Position', [.18 .22 .77 .70], 'FontName', 'Arial', ...
    'FontSize', 7, 'Box', 'off');
hold(ax, 'on');
colors = [0 114 178; 213 94 0; 0 158 115; 204 121 167; 230 159 0; 86 180 233] / 255;
styles = {'-', '--', ':', '-.'};
for i = 1:count
    plot(ax, times, traces(i, :), 'LineWidth', 1.2, ...
        'Color', colors(mod(i-1, size(colors, 1))+1, :), 'LineStyle', styles{mod(i-1, 4)+1});
end
xlim(ax, [times(1) times(end)]);
xlabel(ax, 'Time (s)', 'FontName', 'Arial', 'FontSize', 8);
ylabel(ax, 'Mean amplitude (uV)', 'FontName', 'Arial', 'FontSize', 8);
legend(ax, spec.condition_names, 'Location', 'northeast', 'FontName', 'Arial', ...
    'FontSize', 7, 'Interpreter', 'none', 'Box', 'off');
% Printing from this folder avoids gnuplot misquoting apostrophes in a path.
original_directory = pwd;
directory_cleanup = onCleanup(@() cd(original_directory));
cd(figures);
print(fig, 'condition_means.svg', '-dsvg');
print(fig, 'condition_means.pdf', '-dpdf');
print(fig, 'condition_means.png', '-dpng', '-r600');
cd(original_directory);

caption = ['Equal ROI-channel weights and equal epoch weights within each condition. ' ...
    'The measurement window includes both endpoints. No error bars or statistical inference.'];
write_text(fullfile(figures, 'CAPTIONS.md'), [caption sprintf('\n')]);
rows = '';
for i = 1:count
    rows = [rows sprintf('<tr><th>%s</th><td data-condition-index="%d" data-value-uv="%.17g">%.17g uV</td><td>%d</td></tr>\n', ...
        escape_html(spec.condition_names{i}), i, means(i), means(i), epoch_counts(i))];
end
document = sprintf(['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">' ...
    '<title>AEA native MATLAB ERP means</title><style>' ...
    'body{font-family:Arial,Helvetica,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.5}' ...
    'td,th{text-align:left;padding:.4rem 1rem .4rem 0}img{max-width:100%%}</style></head><body>' ...
    '<h1>AEA native MATLAB ERP means</h1><p>Input: <code>%s</code></p>' ...
    '<p>ROI: %s. Inclusive measurement window: %.17g to %.17g s (%d samples).</p>' ...
    '<table><thead><tr><th>Condition</th><th>Mean</th><th>Epochs</th></tr></thead><tbody>%s</tbody></table>' ...
    '<p>%s minus %s: <span data-metric="contrast" data-value-uv="%.17g">%.17g uV</span>.</p>' ...
    '<figure><img src="../figure-stage/condition_means.svg" alt="Condition mean traces">' ...
    '<figcaption>%s</figcaption></figure>' ...
    '<p>Only arithmetic means were calculated in MATLAB/EEGLAB. Existing epochs and source files were retained. ' ...
    'No filtering, reference change, ICA, baseline correction, rejection, statistical tests or uncertainty estimation were applied.</p>' ...
    '<p>EEGLAB samples are microvolts; no MNE volt conversion was applied. See results.json, ' ...
    'analysis-spec.json, plot_data.json, ENVIRONMENT.json and run_analysis.m in the output folder. ' ...
    'A fixed synthetic example verifies engineering integration, not general EEG reliability.</p></body></html>\n'], ...
    escape_html(input_set), escape_html(strjoin(spec.roi, ', ')), window(1), window(2), numel(samples), ...
    rows, escape_html(spec.condition_names{contrast(1)}), escape_html(spec.condition_names{contrast(2)}), ...
    results.contrast_uV, results.contrast_uV, caption);
write_text(fullfile(report_dir, 'report.html'), document);
write_text(fullfile(output_dir, 'run_analysis.m'), sprintf([ ...
    '%% Replay the same explicit specification into a new output directory.\n' ...
    'function results = run_analysis(new_output_dir)\n' ...
    'addpath(%s);\naddpath(genpath(%s));\naddpath(%s);\n' ...
    'spec = jsondecode(fileread(%s));\n' ...
    'spec.condition_names = reshape(spec.condition_names, 1, []);\n' ...
    'spec.roi = reshape(spec.roi, 1, []);\n' ...
    '%% Use the epoch lists as recorded in the original executable call.\n' ...
    '%s\nresults = aea_erp_mean(%s, new_output_dir, spec);\nend\n'], ...
    literal(fileparts(mfilename('fullpath'))), literal(fileparts(fileparts(which('pop_loadset')))), ...
    literal(fileparts(which('dipfitdefs'))), ...
    literal(fullfile(output_dir, 'analysis-spec.json')), epoch_list_code(spec.condition_epochs), literal(input_set)));
end

function code = epoch_list_code(lists)
items = cellfun(@(x) mat2str(x), lists, 'UniformOutput', false);
code = ['spec.condition_epochs = {' strjoin(items, ', ') '};'];
end

function text = literal(value)
text = [char(39) strrep(value, char(39), [char(39) char(39)]) char(39)];
end

function text = escape_html(text)
text = strrep(text, '&', '&amp;'); text = strrep(text, '<', '&lt;');
text = strrep(text, '>', '&gt;'); text = strrep(text, '"', '&quot;');
end

function write_text(path, text)
fid = fopen(path, 'w', 'n', 'UTF-8');
if fid < 0, error('AEA:WriteFailed', 'Cannot write %s', path); end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '%s', text);
end
