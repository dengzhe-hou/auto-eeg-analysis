% AEA backend template — ERP preprocess + average, EEGLAB (MATLAB or GNU Octave)
% =============================================================================
% Emitted when tools/env/resolve_backend.py resolves `erp.preprocess_average` to `eeglab`.
% Fill the SPEC block, then run. Everything below the SPEC block is fixed.
%
% WHY THIS TEMPLATE PINS SO MUCH
% -------------------------------
% Cross-toolbox agreement is a property of how completely the specification is pinned, not of the
% toolbox. Running this analysis under each toolbox's own defaults produced per-subject differences
% of up to 43% of the group effect; pinning the specification brought three independently
% implemented toolboxes within 0.05 uV of each other (r = 1.0000).
% See https://github.com/dengzhe-hou/auto-eeg-analysis/blob/995f53d42cc74205b164e8711d4b289b8c2ad3a1/tools/benchmark/CROSS_TOOLBOX_EVAL.md.
%
% The four conventions below are the ones that were measured to matter. Do not delete them and do
% not fall back on a toolbox default — an unstated convention is not a neutral choice, it is a
% silent one.
%
% MEASURED AGREEMENT with the certified MNE reference (5 ERP CORE components):
%   worst-case per-subject |delta| 0.233 uV | min CCC 0.9953 | group conclusion reproduced 5/5
% Group conclusions were robust. Per-subject values were not: individual-differences analyses and
% single-subject classification are sensitive at this level.

more off;

%% ==================== SPEC — fill this in ====================
SPEC = struct();

% --- data ---
SPEC.data_root   = '<PATH TO BIDS-LIKE ROOT>';   % expects <root>/<sub>/eeg/<sub>_task-<task>_eeg.set
SPEC.task        = '<TASK>';
SPEC.subjects    = {};                            % {} = every sub-*/ found
SPEC.drop_channels = {'HEOG_left','HEOG_right','VEOG_lower'};

% --- filter -------------------------------------------------------------
% PIN filter.cutoff_convention: does the number below name the PASSBAND EDGE or the -6 dB POINT?
%   'passband'  -> matches MNE and EEGLAB's own idiom (-6 dB lands df/2 below the stated value)
%   'minus6db'  -> matches FieldTrip's idiom
% pop_eegfiltnew already treats its argument as the passband edge, so 'passband' is a no-op here
% and 'minus6db' shifts the request. Stating it makes the generated FieldTrip code agree.
SPEC.filter.cutoff_convention = 'passband';
SPEC.filter.l_freq = 0.1;
SPEC.filter.h_freq = 30;
% PIN filter.transition_width: EEGLAB's heuristic gives 0.1 Hz here; state it rather than inherit it.
SPEC.filter.transition_hz = 0.1;

% --- resample -----------------------------------------------------------
% PIN resample.algorithm. NOTE: without Octave Forge `signal`, pop_resample silently falls back to
% cubic-spline interpolation. That fallback is what AEA's validation actually measured, so it is
% acceptable — but it must be recorded, not discovered later.
SPEC.resample_hz = 256;

% --- epoching -----------------------------------------------------------
SPEC.epoch      = [-0.2 0.5];      % seconds
SPEC.baseline   = [-0.2 0];        % seconds; use [] for no baseline correction

% --- artefact rejection -------------------------------------------------
% PIN reject.criterion: 'p2p' (max-min within the epoch, = MNE's `reject`) or 'abs'
% (|amplitude| anywhere, = EEGLAB's pop_eegthresh idiom) or 'none'.
% These are NOT the same rule. On MMN they retained 130 vs 185 deviant epochs for the same subject.
SPEC.reject.criterion   = 'p2p';
SPEC.reject.threshold_uV = 100;

% --- conditions ---------------------------------------------------------
% Numeric event codes for the two conditions. The reported difference wave is A - B.
SPEC.cond_A.name  = '<CONDITION A>';
SPEC.cond_A.codes = [];
SPEC.cond_B.name  = '<CONDITION B>';
SPEC.cond_B.codes = [];
SPEC.min_trials_A = 0;
SPEC.min_trials_B = 0;

% --- measurement --------------------------------------------------------
SPEC.roi        = {};              % e.g. {'Fz','FCz','Cz'}
SPEC.window_ms  = [0 0];

% --- output -------------------------------------------------------------
SPEC.out_json   = 'preprocess-stage/backend_eeglab_result.json';
SPEC.eeglab_dir = getenv('EEGLAB_PATH');
%% ================== end SPEC — do not edit below ==================

if isempty(SPEC.eeglab_dir)
  error('EEGLAB_PATH is not set. Run tools/env/check_env.sh and install EEGLAB.');
end
% `eeglab nogui` fails under Octave; adding the source trees directly works on both engines.
addpath(genpath(fullfile(SPEC.eeglab_dir, 'functions')));
addpath(genpath(fullfile(SPEC.eeglab_dir, 'plugins')));

% Apply the pinned cutoff convention. pop_eegfiltnew's argument IS the passband edge.
lo = SPEC.filter.l_freq; hi = SPEC.filter.h_freq;
switch lower(SPEC.filter.cutoff_convention)
  case 'passband'   % no shift
  case 'minus6db'
    lo = lo + SPEC.filter.transition_hz / 2;
    hi = hi - SPEC.filter.transition_hz / 2;
  otherwise
    error('SPEC.filter.cutoff_convention must be ''passband'' or ''minus6db''');
end

subs_wanted = SPEC.subjects;
if isempty(subs_wanted)
  d = dir(fullfile(SPEC.data_root, 'sub-*'));
  subs_wanted = {d([d.isdir]).name};
end

subs = {}; vals = []; na = []; nb = []; skipped = {};
for i = 1:numel(subs_wanted)
  sid = subs_wanted{i};
  fdir = fullfile(SPEC.data_root, sid, 'eeg');
  fname = sprintf('%s_task-%s_eeg.set', sid, SPEC.task);
  if ~exist(fullfile(fdir, fname), 'file')
    skipped{end+1} = sprintf('%s: no %s', sid, fname); continue;
  end
  try
    EEG = pop_loadset('filename', fname, 'filepath', fdir);

    drop = SPEC.drop_channels(ismember(SPEC.drop_channels, {EEG.chanlocs.labels}));
    if ~isempty(drop); EEG = pop_select(EEG, 'nochannel', drop); end

    EEG = pop_eegfiltnew(EEG, lo, hi, [], 0, [], 0);
    if ~isempty(SPEC.resample_hz) && abs(EEG.srate - SPEC.resample_hz) > 1
      EEG = pop_resample(EEG, SPEC.resample_hz);
    end
    EEG = pop_reref(EEG, []);

    % Relabel to canonical 'A'/'B'. Every type is written back as a STRING: EEG.event.type can be
    % char in one dataset and double in another, and pop_epoch rejects a mixed-type event field.
    for k = 1:numel(EEG.event)
      t = EEG.event(k).type;
      if ischar(t); v = str2double(t); else; v = double(t); end
      if ~isnan(v) && ismember(v, SPEC.cond_A.codes)
        EEG.event(k).type = 'A';
      elseif ~isnan(v) && ismember(v, SPEC.cond_B.codes)
        EEG.event(k).type = 'B';
      elseif ischar(t)
        EEG.event(k).type = t;
      else
        EEG.event(k).type = num2str(t);
      end
    end

    EEG = pop_epoch(EEG, {'A','B'}, SPEC.epoch);
    if ~isempty(SPEC.baseline)
      % Sample grid rarely lands exactly on the requested edge; clamp to the first sample.
      EEG = pop_rmbase(EEG, [max(EEG.times(1), SPEC.baseline(1)*1000), SPEC.baseline(2)*1000]);
    end

    switch lower(SPEC.reject.criterion)
      case 'p2p'
        pp = squeeze(max(EEG.data, [], 2) - min(EEG.data, [], 2));   % nbchan x ntrials
        bad = find(any(pp > SPEC.reject.threshold_uV, 1));
        if ~isempty(bad); EEG = pop_rejepoch(EEG, bad, 0); end
      case 'abs'
        EEG = pop_eegthresh(EEG, 1, 1:EEG.nbchan, -SPEC.reject.threshold_uV, ...
                            SPEC.reject.threshold_uV, SPEC.epoch(1), SPEC.epoch(2), 0, 1);
      case 'none'
      otherwise
        error('SPEC.reject.criterion must be ''p2p'', ''abs'' or ''none''');
    end

    % Split on the TIME-LOCKING event (latency 0), not the first event in the epoch.
    lab = cell(1, numel(EEG.epoch));
    for e = 1:numel(EEG.epoch)
      t = EEG.epoch(e).eventtype; l = EEG.epoch(e).eventlatency;
      if ~iscell(t); t = {t}; end
      if ~iscell(l); l = {l}; end
      lat = zeros(1, numel(l));
      for j = 1:numel(l); lat(j) = abs(double(l{j})); end
      [~, j0] = min(lat);
      tj = t{j0}; if ~ischar(tj); tj = num2str(tj); end
      lab{e} = tj;
    end
    isA = strcmp(lab, 'A'); isB = strcmp(lab, 'B');

    if sum(isA) < SPEC.min_trials_A || sum(isB) < SPEC.min_trials_B
      skipped{end+1} = sprintf('%s: %d/%d trials below minimum %d/%d', ...
                               sid, sum(isA), sum(isB), SPEC.min_trials_A, SPEC.min_trials_B);
      continue;
    end

    dwave = mean(EEG.data(:,:,isA), 3) - mean(EEG.data(:,:,isB), 3);
    ridx = [];
    for c = 1:numel(SPEC.roi)
      k = find(strcmpi({EEG.chanlocs.labels}, SPEC.roi{c}));
      if isempty(k)
        error('%s: ROI channel %s not present', sid, SPEC.roi{c});
      end
      ridx(end+1) = k(1);
    end
    tmask = EEG.times >= SPEC.window_ms(1) & EEG.times <= SPEC.window_ms(2);
    v = mean(mean(dwave(ridx, tmask)));

    subs{end+1} = sid; vals(end+1) = v; na(end+1) = sum(isA); nb(end+1) = sum(isB);
    printf('%s %s-%s = %.4f uV (a=%d b=%d)\n', sid, SPEC.cond_A.name, SPEC.cond_B.name, ...
           v, sum(isA), sum(isB));
  catch err
    skipped{end+1} = sprintf('%s: ERROR %s', sid, err.message);
    printf('%s ERROR %s\n', sid, err.message);
  end
end

% Never report an empty run as a success: a mean over an empty set is 0, which reads as a result.
if isempty(vals)
  error(['no subject produced a value — refusing to write a result file. ' ...
         'Check SPEC.cond_*.codes against the dataset''s event values.']);
end

odir = fileparts(SPEC.out_json);
if ~isempty(odir) && ~exist(odir, 'dir'); mkdir(odir); end
fid = fopen(SPEC.out_json, 'w');
fprintf(fid, '{\n  "backend": "eeglab",\n  "task": "%s",\n', SPEC.task);
fprintf(fid, '  "pinned": {"cutoff_convention": "%s", "transition_hz": %g, "reject_criterion": "%s", "reject_threshold_uV": %g, "resample_hz": %g},\n', ...
        SPEC.filter.cutoff_convention, SPEC.filter.transition_hz, SPEC.reject.criterion, ...
        SPEC.reject.threshold_uV, SPEC.resample_hz);
fprintf(fid, '  "contrast": "%s - %s",\n', SPEC.cond_A.name, SPEC.cond_B.name);
fprintf(fid, '  "per_subject": {');
for k = 1:numel(subs)
  if k > 1; fprintf(fid, ', '); end
  fprintf(fid, '"%s": %.4f', subs{k}, vals(k));
end
fprintf(fid, '},\n  "n_trials": {');
for k = 1:numel(subs)
  if k > 1; fprintf(fid, ', '); end
  fprintf(fid, '"%s": [%d, %d]', subs{k}, na(k), nb(k));
end
fprintf(fid, '},\n  "excluded": [');
for k = 1:numel(skipped)
  if k > 1; fprintf(fid, ', '); end
  fprintf(fid, '"%s"', strrep(skipped{k}, '"', ''''));
end
fprintf(fid, '],\n  "n_analyzed": %d,\n  "grand_mean_uV": %.4f\n}\n', numel(vals), mean(vals));
fclose(fid);
printf('DONE n=%d grand=%.4f uV -> %s\n', numel(vals), mean(vals), SPEC.out_json);
