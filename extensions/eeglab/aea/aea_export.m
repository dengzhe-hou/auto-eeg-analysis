% AEA_EXPORT - Save a copy of the current EEGLAB dataset for an AEA study.
%
% info = aea_export(EEG, project_dir)
% Writes input/imported.set + .fdt, EEGLAB_EXPORT.json, input/events.json and
% input/processing_history.txt. The EEG argument and its source files are not
% changed. No filtering, referencing, epoching or ICA is performed.
function info = aea_export(EEG, project_dir)
if isempty(EEG) || numel(EEG) ~= 1 || EEG.nbchan < 1 || EEG.pnts < 1
    error('AEA:NoDataset', 'Load one EEG dataset before exporting.');
end
if ~isnumeric(EEG.data)
    error('AEA:DataNotLoaded', 'Load the current EEG samples into memory before exporting.');
end
if EEG.trials == 1 && isfield(EEG, 'epoch') && ~isempty(EEG.epoch)
    error('AEA:SingleEpoch', 'This first adapter supports continuous data or at least two epochs. The single-epoch dataset was not exported.');
end
input_dir = fullfile(project_dir, 'input');
if exist(fullfile(input_dir, 'imported.set'), 'file') || exist(fullfile(input_dir, 'imported.fdt'), 'file')
    error('AEA:ExistingExport', 'This folder already has an EEG export. Choose a new study folder to keep the previous input.');
end
if ~exist(input_dir, 'dir'), mkdir(input_dir); end
% Use EEGLAB's writer and explicit two-file v7 layout, readable by MNE.
% Standard EEGLAB saving stores the samples as float32; retain the live EEG.
pop_saveset(EEG, 'filename', 'imported.set', 'filepath', input_dir, ...
    'savemode', 'twofiles', 'version', '7');
kind = 'continuous';
if EEG.trials > 1, kind = 'epoched'; end
labels = {EEG.chanlocs.labels};
types = repmat({''}, 1, numel(labels));
if isfield(EEG.chanlocs, 'type'), types = {EEG.chanlocs.type}; end
info = struct('format_version', 1, 'dataset_kind', kind, ...
    'input_file', 'input/imported.set', 'samples_unit', 'uV', ...
    'saved_sample_type', 'float32', 'srate', EEG.srate, ...
    'n_channels', EEG.nbchan, 'n_samples_per_epoch', EEG.pnts, 'n_epochs', EEG.trials, ...
    'epoch_tmin_s', EEG.xmin, 'channel_labels', {labels}, 'channel_types', {types}, ...
    'processing_status', 'requires_researcher_confirmation', ...
    'has_ica_weights', isfield(EEG, 'icaweights') && ~isempty(EEG.icaweights));
if isfield(EEG, 'setname'), info.setname = EEG.setname; end
info.source_filename = '';
if isfield(EEG, 'filename'), info.source_filename = EEG.filename; end
events = struct('latency_unit', 'one_based_sample', 'duration_unit', 'sample', ...
    'note', 'Original EEGLAB events; epoched latency is in the concatenated sample coordinate. Condition meanings are not inferred.', ...
    'events', {EEG.event});
aea_write_json(fullfile(input_dir, 'events.json'), events);
fid = fopen(fullfile(input_dir, 'processing_history.txt'), 'w', 'n', 'UTF-8');
if fid < 0, error('AEA:WriteFailed', 'Cannot write processing history.'); end
cleanup = onCleanup(@() fclose(fid));
if isfield(EEG, 'history'), fprintf(fid, '%s\n', EEG.history); end
aea_write_json(fullfile(project_dir, 'EEGLAB_EXPORT.json'), info);
end
