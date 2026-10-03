% erpcore_fieldtrip.m — FieldTrip/Octave implementation of the AEA harmonized-minimal
% ERP CORE pipelines. This is the *third* toolbox arm of the cross-tool benchmark
% (MNE-Python / EEGLAB / FieldTrip), added to test whether the certified values survive
% a toolbox with an entirely different data model (trial-struct rather than 3-D array)
% and its own filter, resampler and averaging code.
%
% Usage:
%   export OCTAVE_HOME=$HOME/miniconda3/envs/octave
%   COMP=N170 $OCTAVE_HOME/bin/octave-cli --no-gui --quiet tools/benchmark/erpcore_fieldtrip.m
%
% Environment variables:
%   COMP        MMN | P3 | N170 | ERN | N400   (default N170)
%   FILTTYPE    firws | but                    (default firws; `but` = Butterworth IIR,
%               a genuinely different filter *class* from MNE's and EEGLAB's FIR)
%   FILTDF      FIR transition-band width in Hz (default: FieldTrip's own 0.2 Hz).
%   CUTOFFCONV  fieldtrip | eeglab  (default fieldtrip). Which convention the stated
%               band edge follows: FieldTrip puts the -6 dB point AT the stated
%               frequency; EEGLAB/MNE treat it as the passband edge and put -6 dB at
%               half a transition band below. Neither is wrong; "0.1 Hz high-pass"
%               simply does not say which is meant.
%   OUTFILE     output JSON path
%   FT_DIR      FieldTrip root (falls back to FIELDTRIP_PATH)
%   AEA_DATA_ROOT  where the ERP CORE datasets live (default $HOME/mne_data)
%   NSUB        subjects to attempt (default 40)
%
% Note on rejection: only the no-rejection components are supported here (P3/N170/ERN/N400)
% plus MMN with peak-to-peak matching MNE's `reject` semantics, implemented explicitly.

more off;
ft_dir = getenv('FT_DIR');
if isempty(ft_dir); ft_dir = getenv('FIELDTRIP_PATH'); end
if isempty(ft_dir)
  error('set FT_DIR (or FIELDTRIP_PATH) to a FieldTrip install dir containing ft_defaults.m');
end
addpath(ft_dir);
ft_defaults;

comp = upper(getenv('COMP')); if isempty(comp); comp = 'N170'; end
filttype = getenv('FILTTYPE'); if isempty(filttype); filttype = 'firws'; end
filtdf = str2double(getenv('FILTDF'));  % [] / NaN -> FieldTrip's own default (0.2 Hz)
if isnan(filtdf); filtdf = []; end
cutoffconv = getenv('CUTOFFCONV'); if isempty(cutoffconv); cutoffconv = 'fieldtrip'; end
data_root = getenv('AEA_DATA_ROOT');
if isempty(data_root); data_root = fullfile(getenv('HOME'), 'mne_data'); end
outfile = getenv('OUTFILE');
nsub = str2double(getenv('NSUB')); if isnan(nsub); nsub = 40; end

switch comp
  case 'MMN'
    droot = fullfile(data_root, 'MNE-erpcoremmn2021-data');
    lo = 0.1; hi = 30;  ep = [-0.2 0.5];  bl = [-0.2 0];
    roi = {'Fz','FCz','Cz'};        win = [0.100 0.250];
    min_a = 50;  min_b = 150;  p2p_uV = 100;
  case 'P3'
    droot = fullfile(data_root, 'erpcore-P3');
    lo = 0.1; hi = 30;  ep = [-0.2 0.8];  bl = [-0.2 0];
    roi = {'Fz','Cz','Pz','CPz'};   win = [0.300 0.500];
    min_a = 30;  min_b = 100;  p2p_uV = 0;
  case 'N170'
    droot = fullfile(data_root, 'erpcore-N170');
    lo = 0.1; hi = 40;  ep = [-0.2 0.5];  bl = [-0.2 0];
    roi = {'PO7','PO8','P7','P8'};  win = [0.130 0.200];
    min_a = 30;  min_b = 30;  p2p_uV = 0;
  case 'ERN'
    droot = fullfile(data_root, 'erpcore-ERN');
    lo = 0.1; hi = 30;  ep = [-0.4 0.6];  bl = [-0.4 -0.2];
    roi = {'FCz','Fz','Cz'};        win = [0.000 0.100];
    min_a = 15;  min_b = 15;  p2p_uV = 0;
  case 'N400'
    droot = fullfile(data_root, 'erpcore-N400');
    lo = 0.1; hi = 30;  ep = [-0.2 0.8];  bl = [-0.2 0];
    roi = {'CPz','Cz','Pz'};        win = [0.300 0.500];
    min_a = 30;  min_b = 30;  p2p_uV = 0;
  otherwise
    error('unknown COMP: %s', comp);
end
if isempty(outfile)
  outfile = sprintf('/tmp/ft_bench/fieldtrip_%s_%s.json', lower(comp), filttype);
end
printf('COMP=%s filttype=%s out=%s\n', comp, filttype, outfile);

fs = 256;
subs = {}; vals = []; na = []; nb = [];
for i = 1:nsub
  sid = sprintf('sub-%03d', i);
  fset = sprintf('%s/%s/eeg/%s_task-%s_eeg.set', droot, sid, sid, comp);
  if ~exist(fset, 'file'); continue; end
  try
    % ---- 1. continuous preprocessing: bandpass + average reference over scalp channels
    cfg = [];
    cfg.dataset    = fset;
    cfg.channel    = {'all', '-HEOG_left', '-HEOG_right', '-VEOG_lower'};
    cfg.continuous = 'yes';
    cfg.bpfilter   = 'yes';
    % Two *separate* unstated filter parameters, both of which "0.1-30 Hz zero-phase FIR"
    % leaves open, and on which the three toolboxes disagree:
    %
    %   (a) transition-band width -- MNE 0.1 Hz low / 7.5 Hz high; EEGLAB 0.1 Hz both;
    %       FieldTrip 0.2 Hz both. Pinned by FILTDF.
    %   (b) what the stated number MEANS -- EEGLAB and MNE treat 0.1 Hz as the PASSBAND
    %       EDGE and place the -6 dB point at 0.05 Hz; FieldTrip treats it as the -6 dB
    %       POINT itself. The same "0.1 Hz high-pass" is therefore a 2x different filter.
    %       Pinned by CUTOFFCONV=eeglab, which shifts the requested band by df/2 so the
    %       -6 dB points land where EEGLAB/MNE put them.
    if strcmpi(cutoffconv, 'eeglab')
      df_ = filtdf; if isempty(df_); df_ = 0.2; end
      cfg.bpfreq = [lo - df_/2, hi + df_/2];
    else
      cfg.bpfreq = [lo hi];
    end
    cfg.bpfilttype = filttype;
    if ~isempty(filtdf); cfg.bpfiltdf = filtdf; end
    cfg.reref      = 'yes';
    cfg.refchannel = 'all';
    data = ft_preprocessing(cfg);

    % ---- 2. downsample 1024 -> 256 Hz by decimation.
    % ft_resampledata needs Octave Forge `signal`, which cannot be built in this
    % environment (no C++ compiler). Decimation is exact here rather than a
    % compromise: the data have just been low-pass filtered at <=40 Hz and the new
    % Nyquist is 128 Hz, so keeping every 4th sample introduces no aliasing. Sample 1
    % is retained, so new sample k maps to time (k-1)/256 s — the same time origin
    % MNE's resampler uses. This is a THIRD independent resampling implementation
    % (MNE: FFT/polyphase; EEGLAB here: cubic-spline interpolation; FieldTrip here:
    % decimation).
    dec = round(data.fsample / fs);
    if abs(data.fsample / dec - fs) > 1e-6
      error('non-integer decimation factor: %g -> %g', data.fsample, fs);
    end
    for t = 1:numel(data.trial)
      data.trial{t} = data.trial{t}(:, 1:dec:end);
      data.time{t}  = data.time{t}(1:dec:end);
    end
    data.fsample = fs;
    if isfield(data, 'sampleinfo'); data = rmfield(data, 'sampleinfo'); end

    % ---- 3. events -> trial definition, using the SAME numeric decoding rule as the
    %        Python reference (.set codes verified identical to the BIDS events.tsv)
    hdr = ft_read_header(fset);
    ev  = ft_read_event(fset);
    codes = []; samples = [];
    for k = 1:numel(ev)
      v = ev(k).value; if isempty(v); v = ev(k).type; end
      if ischar(v); v = str2double(v); else; v = double(v); end
      if isnan(v); continue; end
      cls = 0;
      switch comp
        case 'MMN'
          if v == 70; cls = 1; elseif v == 80; cls = 2; end
        case 'P3'
          if v >= 11 && v <= 55
            if floor(v/10) == mod(v,10); cls = 1; else; cls = 2; end
          end
        case 'N170'
          if v >= 1 && v <= 40; cls = 1; elseif v >= 41 && v <= 80; cls = 2; end
        case 'ERN'
          if v >= 111 && v <= 222
            if floor(v/100) == mod(v,10); cls = 2; else; cls = 1; end
          end
        case 'N400'
          if v == 221 || v == 222; cls = 1; elseif v == 211 || v == 212; cls = 2; end
      end
      if cls > 0
        % ev(k).sample is at the ORIGINAL rate -> rescale to the resampled rate
        codes(end+1)   = cls;
        samples(end+1) = round((ev(k).sample - 1) * fs / hdr.Fs) + 1;
      end
    end

    pre  = round(ep(1) * fs);   % negative
    post = round(ep(2) * fs);
    ntime = numel(data.time{1});
    trl = [];
    for k = 1:numel(codes)
      b = samples(k) + pre;  e = samples(k) + post;
      if b >= 1 && e <= ntime
        trl(end+1, :) = [b e pre codes(k)];   %#ok<AGROW>
      end
    end
    if isempty(trl); printf('%s SKIP no trials\n', sid); continue; end

    cfg = []; cfg.trl = trl;
    data = ft_redefinetrial(cfg, data);

    % ---- 4. baseline correction
    cfg = []; cfg.demean = 'yes'; cfg.baselinewindow = bl;
    data = ft_preprocessing(cfg, data);

    cond = trl(:, 4);

    % ---- 5. optional peak-to-peak rejection, matching MNE's `reject` semantics
    if p2p_uV > 0
      keep = true(numel(data.trial), 1);
      for t = 1:numel(data.trial)
        x = data.trial{t};
        if any(max(x, [], 2) - min(x, [], 2) > p2p_uV); keep(t) = false; end
      end
      cfg = []; cfg.trials = find(keep);
      data = ft_redefinetrial(cfg, data);
      cond = cond(keep);
    end

    if sum(cond == 1) < min_a || sum(cond == 2) < min_b
      printf('%s SKIP a=%d b=%d\n', sid, sum(cond == 1), sum(cond == 2));
      continue;
    end

    % ---- 6. condition averages and difference wave
    cfg = []; cfg.trials = find(cond == 1); avgA = ft_timelockanalysis(cfg, data);
    cfg = []; cfg.trials = find(cond == 2); avgB = ft_timelockanalysis(cfg, data);
    dwave = avgA.avg - avgB.avg;

    ridx = [];
    for c = 1:numel(roi)
      k = find(strcmpi(avgA.label, roi{c}));
      if ~isempty(k); ridx(end+1) = k(1); end
    end
    tmask = avgA.time >= win(1) & avgA.time <= win(2);
    v = mean(mean(dwave(ridx, tmask)));

    subs{end+1} = sid; vals(end+1) = v;
    na(end+1) = sum(cond == 1); nb(end+1) = sum(cond == 2);
    printf('%s %s=%.4f uV (a=%d b=%d)\n', sid, comp, v, na(end), nb(end));
  catch err
    printf('%s ERROR %s\n', sid, err.message);
  end
end

odir = fileparts(outfile);
if ~isempty(odir) && ~exist(odir, 'dir'); mkdir(odir); end
fid = fopen(outfile, 'w');
fprintf(fid, '{"component": "%s", "reject_mode": "%s", "toolbox": "FieldTrip/Octave", "filttype": "%s", "filtdf": "%s",\n', ...
        comp, merge(p2p_uV > 0, 'p2p', 'none'), filttype, ...
        merge(isempty(filtdf), 'default', num2str(filtdf)));
fprintf(fid, ' "cutoff_convention": "%s",\n', cutoffconv);
fprintf(fid, ' "per_subject": {');
for k = 1:numel(subs)
  if k > 1; fprintf(fid, ', '); end
  fprintf(fid, '"%s": %.4f', subs{k}, vals(k));
end
fprintf(fid, '},\n "n_trials": {');
for k = 1:numel(subs)
  if k > 1; fprintf(fid, ', '); end
  fprintf(fid, '"%s": [%d, %d]', subs{k}, na(k), nb(k));
end
fprintf(fid, '},\n "n_analyzed": %d, "grand_mean_uV": %.4f}\n', numel(vals), mean(vals));
fclose(fid);
printf('DONE %s n=%d grand=%.4f uV -> %s\n', comp, numel(vals), mean(vals), outfile);
