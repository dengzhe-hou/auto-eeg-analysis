% AEA backend template — ERP preprocess + average, FieldTrip (MATLAB or GNU Octave)
% =============================================================================
% Emitted when tools/env/resolve_backend.py resolves `erp.preprocess_average` to `fieldtrip`.
% Fill the SPEC block, then run. Everything below the SPEC block is fixed.
%
% WHY THIS TEMPLATE PINS SO MUCH
% -------------------------------
% This backend is the reason the pinning exists. Under FieldTrip's own defaults the P3 analysis
% disagreed with the certified reference by up to 0.721 uV per subject — 43% of the group effect.
% The cause was NOT the toolbox: FieldTrip reads a stated band edge as the -6 dB POINT while MNE
% and EEGLAB read it as the PASSBAND EDGE, so "a 0.1 Hz high-pass" is a 2x different filter.
% Pinning that one convention took the same FieldTrip code to 0.050 uV, CCC 0.999943, r = 1.0000 —
% better agreement than EEGLAB. See tools/benchmark/CROSS_TOOLBOX_EVAL.md sec 2b.
%
% MEASURED AGREEMENT with the certified MNE reference, at FieldTrip's own defaults (5 components):
%   worst-case per-subject |delta| 0.721 uV | min CCC 0.9928 | group conclusion reproduced 5/5
% With the filter fully pinned (P3): 0.050 uV, r 1.0000.
%
% Group conclusions were robust either way. Per-subject values were not — the unpinned run flipped
% the sign for 2 of 20 subjects, both of whom had a near-zero effect to begin with.

more off;

%% ==================== SPEC — fill this in ====================
SPEC = struct();

% --- data ---
SPEC.data_root   = '<PATH TO BIDS-LIKE ROOT>';   % expects <root>/<sub>/eeg/<sub>_task-<task>_eeg.set
SPEC.task        = '<TASK>';
SPEC.subjects    = {};                            % {} = every sub-*/ found
SPEC.drop_channels = {'HEOG_left','HEOG_right','VEOG_lower'};

% --- filter -------------------------------------------------------------
% PIN filter.cutoff_convention. THIS IS THE ONE THAT MATTERS MOST FOR FIELDTRIP.
%   'passband'  -> the stated number is the passband edge (MNE / EEGLAB convention).
%                  The template shifts cfg.bpfreq by transition/2 so the -6 dB points match.
%   'minus6db'  -> the stated number is the -6 dB point (FieldTrip's own convention, unshifted).
% Choose 'passband' whenever the numbers are meant to be comparable to an MNE or EEGLAB result.
SPEC.filter.cutoff_convention = 'passband';
SPEC.filter.l_freq = 0.1;
SPEC.filter.h_freq = 30;
% PIN filter.transition_width: FieldTrip's default is 0.2 Hz, MNE/EEGLAB use 0.1 Hz at the low edge.
SPEC.filter.transition_hz = 0.1;

% --- resample -----------------------------------------------------------
% PIN resample.algorithm:
%   'ft'         -> ft_resampledata (requires Octave Forge `signal` under Octave)
%   'decimate'   -> keep every Nth sample. EXACT, not a compromise, when the data are already
%                   band-limited below the new Nyquist (which the band-pass above guarantees),
%                   and the only option when `signal` cannot be built. This is what AEA's
%                   cross-toolbox validation measured.
SPEC.resample_hz  = 256;
SPEC.resample_algo = 'decimate';

% --- epoching -----------------------------------------------------------
SPEC.epoch      = [-0.2 0.5];      % seconds
SPEC.baseline   = [-0.2 0];        % seconds; [] for none

% --- artefact rejection -------------------------------------------------
% PIN reject.criterion: FieldTrip has no idiomatic default here, which makes it easy to omit
% silently. 'p2p' matches MNE's `reject`; 'abs' matches EEGLAB's pop_eegthresh; 'none' keeps all.
SPEC.reject.criterion    = 'p2p';
SPEC.reject.threshold_uV = 100;

% --- conditions ---------------------------------------------------------
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
SPEC.out_json = 'preprocess-stage/backend_fieldtrip_result.json';
SPEC.ft_dir   = getenv('FIELDTRIP_PATH');
%% ================== end SPEC — do not edit below ==================

if isempty(SPEC.ft_dir)
  error('FIELDTRIP_PATH is not set. Run tools/env/check_env.sh and install FieldTrip.');
end
addpath(SPEC.ft_dir);
ft_defaults;

% Apply the pinned cutoff convention: cfg.bpfreq names the -6 dB points in FieldTrip.
lo = SPEC.filter.l_freq; hi = SPEC.filter.h_freq;
switch lower(SPEC.filter.cutoff_convention)
  case 'passband'
    lo = lo - SPEC.filter.transition_hz / 2;
    hi = hi + SPEC.filter.transition_hz / 2;
  case 'minus6db'   % no shift — FieldTrip's own reading
  otherwise
    error('SPEC.filter.cutoff_convention must be ''passband'' or ''minus6db''');
end

fs = SPEC.resample_hz;
subs_wanted = SPEC.subjects;
if isempty(subs_wanted)
  d = dir(fullfile(SPEC.data_root, 'sub-*'));
  subs_wanted = {d([d.isdir]).name};
end

subs = {}; vals = []; na = []; nb = []; skipped = {};
for i = 1:numel(subs_wanted)
  sid = subs_wanted{i};
  fset = fullfile(SPEC.data_root, sid, 'eeg', sprintf('%s_task-%s_eeg.set', sid, SPEC.task));
  if ~exist(fset, 'file')
    skipped{end+1} = sprintf('%s: no .set', sid); continue;
  end
  try
    cfg = [];
    cfg.dataset    = fset;
    cfg.continuous = 'yes';
    cfg.channel    = [{'all'}, cellfun(@(c) ['-' c], SPEC.drop_channels, 'UniformOutput', false)];
    cfg.bpfilter   = 'yes';
    cfg.bpfreq     = [lo hi];
    cfg.bpfilttype = 'firws';
    cfg.bpfiltdf   = SPEC.filter.transition_hz;
    cfg.reref      = 'yes';
    cfg.refchannel = 'all';
    data = ft_preprocessing(cfg);

    switch lower(SPEC.resample_algo)
      case 'ft'
        cfg = []; cfg.resamplefs = fs; cfg.detrend = 'no';
        data = ft_resampledata(cfg, data);
      case 'decimate'
        dec = round(data.fsample / fs);
        if abs(data.fsample / dec - fs) > 1e-6
          error('non-integer decimation factor %g -> %g; use resample_algo=''ft''', data.fsample, fs);
        end
        for t = 1:numel(data.trial)
          data.trial{t} = data.trial{t}(:, 1:dec:end);
          data.time{t}  = data.time{t}(1:dec:end);
        end
        data.fsample = fs;
        if isfield(data, 'sampleinfo'); data = rmfield(data, 'sampleinfo'); end
      otherwise
        error('SPEC.resample_algo must be ''ft'' or ''decimate''');
    end

    hdr = ft_read_header(fset);
    ev  = ft_read_event(fset);
    codes = []; samples = [];
    for k = 1:numel(ev)
      v = ev(k).value; if isempty(v); v = ev(k).type; end
      if ischar(v); v = str2double(v); else; v = double(v); end
      if isnan(v); continue; end
      cls = 0;
      if ismember(v, SPEC.cond_A.codes); cls = 1;
      elseif ismember(v, SPEC.cond_B.codes); cls = 2; end
      if cls > 0
        codes(end+1)   = cls;
        samples(end+1) = round((ev(k).sample - 1) * fs / hdr.Fs) + 1;
      end
    end

    pre = round(SPEC.epoch(1) * fs); post = round(SPEC.epoch(2) * fs);
    ntime = numel(data.time{1});
    trl = [];
    for k = 1:numel(codes)
      b = samples(k) + pre; e = samples(k) + post;
      if b >= 1 && e <= ntime; trl(end+1, :) = [b e pre codes(k)]; end
    end
    if isempty(trl)
      skipped{end+1} = sprintf('%s: no trials matched SPEC.cond_*.codes', sid); continue;
    end

    cfg = []; cfg.trl = trl; data = ft_redefinetrial(cfg, data);

    if ~isempty(SPEC.baseline)
      cfg = []; cfg.demean = 'yes'; cfg.baselinewindow = SPEC.baseline;
      data = ft_preprocessing(cfg, data);
    end

    cond = trl(:, 4);
    switch lower(SPEC.reject.criterion)
      case {'p2p', 'abs'}
        keep = true(numel(data.trial), 1);
        for t = 1:numel(data.trial)
          x = data.trial{t};
          if strcmpi(SPEC.reject.criterion, 'p2p')
            over = any(max(x, [], 2) - min(x, [], 2) > SPEC.reject.threshold_uV);
          else
            over = any(max(abs(x), [], 2) > SPEC.reject.threshold_uV);
          end
          if over; keep(t) = false; end
        end
        cfg = []; cfg.trials = find(keep);
        data = ft_redefinetrial(cfg, data);
        cond = cond(keep);
      case 'none'
      otherwise
        error('SPEC.reject.criterion must be ''p2p'', ''abs'' or ''none''');
    end

    if sum(cond == 1) < SPEC.min_trials_A || sum(cond == 2) < SPEC.min_trials_B
      skipped{end+1} = sprintf('%s: %d/%d trials below minimum %d/%d', sid, ...
                               sum(cond == 1), sum(cond == 2), SPEC.min_trials_A, SPEC.min_trials_B);
      continue;
    end

    cfg = []; cfg.trials = find(cond == 1); avgA = ft_timelockanalysis(cfg, data);
    cfg = []; cfg.trials = find(cond == 2); avgB = ft_timelockanalysis(cfg, data);
    dwave = avgA.avg - avgB.avg;

    ridx = [];
    for c = 1:numel(SPEC.roi)
      k = find(strcmpi(avgA.label, SPEC.roi{c}));
      if isempty(k); error('%s: ROI channel %s not present', sid, SPEC.roi{c}); end
      ridx(end+1) = k(1);
    end
    tmask = avgA.time >= SPEC.window_ms(1)/1000 & avgA.time <= SPEC.window_ms(2)/1000;
    v = mean(mean(dwave(ridx, tmask)));

    subs{end+1} = sid; vals(end+1) = v;
    na(end+1) = sum(cond == 1); nb(end+1) = sum(cond == 2);
    printf('%s %s-%s = %.4f uV (a=%d b=%d)\n', sid, SPEC.cond_A.name, SPEC.cond_B.name, ...
           v, na(end), nb(end));
  catch err
    skipped{end+1} = sprintf('%s: ERROR %s', sid, err.message);
    printf('%s ERROR %s\n', sid, err.message);
  end
end

% Never report an empty run as a success — a mean over an empty set is 0, which reads as a result.
if isempty(vals)
  error(['no subject produced a value — refusing to write a result file. ' ...
         'Check SPEC.cond_*.codes against the dataset''s event values.']);
end

odir = fileparts(SPEC.out_json);
if ~isempty(odir) && ~exist(odir, 'dir'); mkdir(odir); end
fid = fopen(SPEC.out_json, 'w');
fprintf(fid, '{\n  "backend": "fieldtrip",\n  "task": "%s",\n', SPEC.task);
fprintf(fid, '  "pinned": {"cutoff_convention": "%s", "transition_hz": %g, "reject_criterion": "%s", "reject_threshold_uV": %g, "resample_hz": %g, "resample_algo": "%s"},\n', ...
        SPEC.filter.cutoff_convention, SPEC.filter.transition_hz, SPEC.reject.criterion, ...
        SPEC.reject.threshold_uV, SPEC.resample_hz, SPEC.resample_algo);
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
