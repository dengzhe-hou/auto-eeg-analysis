% erpcore_eeglab.m — component-parameterized EEGLAB/Octave implementation of the
% AEA harmonized-minimal ERP CORE pipelines, for cross-toolbox certification.
%
% This is the *independent toolbox* arm of the benchmark: different language, different
% file reader, independently implemented FIR filter, resampler, referencing and epoch
% rejection. The contrast is held identical (same subjects, same event codes) so that
% only the implementation differs.
%
% Usage:
%   export OCTAVE_HOME=$HOME/miniconda3/envs/octave   # conda Octave has an uninitialised load path
%   COMP=P3 $OCTAVE_HOME/bin/octave-cli --no-gui --quiet tools/benchmark/erpcore_eeglab.m
%
% Environment variables:
%   COMP         MMN | P3 | N170 | ERN | N400          (default MMN)
%   REJECT_MODE  none | abs | p2p                      (default: per-component)
%                  abs = pop_eegthresh, |amplitude| > T           (EEGLAB idiom)
%                  p2p = max-min within epoch > T                 (MNE's `reject` semantics)
%   OUTFILE      output JSON path
%   EEGLAB_DIR   EEGLAB checkout (falls back to EEGLAB_PATH)
%   AEA_DATA_ROOT  where the ERP CORE datasets live (default $HOME/mne_data)
%   NSUB         number of subjects to attempt (default 40)

more off;
eeglab_dir = getenv('EEGLAB_DIR');
if isempty(eeglab_dir); eeglab_dir = getenv('EEGLAB_PATH'); end
if isempty(eeglab_dir)
  error('set EEGLAB_DIR (or EEGLAB_PATH) to an EEGLAB install dir');
end
addpath(genpath(fullfile(eeglab_dir, 'functions')));
addpath(genpath(fullfile(eeglab_dir, 'plugins')));

comp = upper(getenv('COMP')); if isempty(comp); comp = 'MMN'; end
reject_mode = lower(getenv('REJECT_MODE'));
data_root = getenv('AEA_DATA_ROOT');
if isempty(data_root); data_root = fullfile(getenv('HOME'), 'mne_data'); end
outfile = getenv('OUTFILE');
nsub = str2double(getenv('NSUB')); if isnan(nsub); nsub = 40; end

% ---------------------------------------------------------------- component contracts
% Mirrors tools/validation/validate_*_group.py exactly. cond_a - cond_b is the reported
% difference wave, measured as the mean over `roi` channels within `win` (ms).
rej_thresh = 100;   % uV, only used when reject_mode is abs/p2p
switch comp
  case 'MMN'    % passive auditory oddball, deviant(70 dB) - standard(80 dB)
    droot = fullfile(data_root, 'MNE-erpcoremmn2021-data');
    lo = 0.1; hi = 30;  ep = [-0.2 0.5];  bl_end_ms = 0;
    roi = {'Fz','FCz','Cz'};        win = [100 250];
    min_a = 50;  min_b = 150;
    if isempty(reject_mode); reject_mode = 'abs'; end
  case 'P3'     % active visual oddball, target - standard
    droot = fullfile(data_root, 'erpcore-P3');
    lo = 0.1; hi = 30;  ep = [-0.2 0.8];  bl_end_ms = 0;
    roi = {'Fz','Cz','Pz','CPz'};   win = [300 500];
    min_a = 30;  min_b = 100;
    if isempty(reject_mode); reject_mode = 'none'; end
  case 'N170'   % face - car
    droot = fullfile(data_root, 'erpcore-N170');
    lo = 0.1; hi = 40;  ep = [-0.2 0.5];  bl_end_ms = 0;
    roi = {'PO7','PO8','P7','P8'};  win = [130 200];
    min_a = 30;  min_b = 30;
    if isempty(reject_mode); reject_mode = 'none'; end
  case 'ERN'    % response-locked flankers, error - correct; pre-response baseline
    droot = fullfile(data_root, 'erpcore-ERN');
    lo = 0.1; hi = 30;  ep = [-0.4 0.6];  bl_end_ms = -200;
    roi = {'FCz','Fz','Cz'};        win = [0 100];
    min_a = 15;  min_b = 15;
    if isempty(reject_mode); reject_mode = 'none'; end
  case 'N400'   % unrelated - related word pairs
    droot = fullfile(data_root, 'erpcore-N400');
    lo = 0.1; hi = 30;  ep = [-0.2 0.8];  bl_end_ms = 0;
    roi = {'CPz','Cz','Pz'};        win = [300 500];
    min_a = 30;  min_b = 30;
    if isempty(reject_mode); reject_mode = 'none'; end
  otherwise
    error('unknown COMP: %s', comp);
end
if isempty(outfile)
  outfile = sprintf('/tmp/eeglab_bench/eeglab_%s_%s.json', lower(comp), reject_mode);
end
printf('COMP=%s reject_mode=%s out=%s\n', comp, reject_mode, outfile);

subs = {}; vals = []; na = []; nb = [];
for i = 1:nsub
  sid = sprintf('sub-%03d', i);
  fdir = sprintf('%s/%s/eeg/', droot, sid);
  fname = sprintf('%s_task-%s_eeg.set', sid, comp);
  if ~exist(fullfile(fdir, fname), 'file'); continue; end
  try
    EEG = pop_loadset('filename', fname, 'filepath', fdir);

    % 1. drop the three EOG channels, keep the 30 scalp electrodes
    EEG = pop_select(EEG, 'nochannel', {'HEOG_left','HEOG_right','VEOG_lower'});
    % 2. bandpass (EEGLAB's own FIR design — independent of MNE's)
    EEG = pop_eegfiltnew(EEG, lo, hi);
    % 3. resample to 256 Hz
    EEG = pop_resample(EEG, 256);
    % 4. average reference over the scalp channels
    EEG = pop_reref(EEG, []);

    % 5. relabel events to canonical 'A'/'B' by the SAME numeric rule the Python
    %    reference uses. Verified: .set event codes are identical to the BIDS
    %    _events.tsv `value` column for all five components.
    for k = 1:length(EEG.event)
      t = EEG.event(k).type;
      if ischar(t); v = str2double(t); else; v = double(t); end
      cls = '';
      if ~isnan(v)
        switch comp
          case 'MMN'
            if v == 70; cls = 'A'; elseif v == 80; cls = 'B'; end
          case 'P3'
            if v >= 11 && v <= 55
              if floor(v/10) == mod(v,10); cls = 'A'; else; cls = 'B'; end
            end
          case 'N170'
            if v >= 1 && v <= 40; cls = 'A'; elseif v >= 41 && v <= 80; cls = 'B'; end
          case 'ERN'
            if v >= 111 && v <= 222
              if floor(v/100) == mod(v,10); cls = 'B'; else; cls = 'A'; end
            end
          case 'N400'
            if v == 221 || v == 222; cls = 'A'; elseif v == 211 || v == 212; cls = 'B'; end
        end
      end
      % Every type is written back as a *string*: ERP CORE stores event types as char
      % for some components (MMN) and as double for others (N170), and pop_epoch
      % rejects a mixed-type event field.
      if isempty(cls)
        if ischar(t); EEG.event(k).type = t; else; EEG.event(k).type = num2str(t); end
      else
        EEG.event(k).type = cls;
      end
    end

    % 6. epoch and baseline-correct
    EEG = pop_epoch(EEG, {'A','B'}, ep);
    EEG = pop_rmbase(EEG, [EEG.times(1) bl_end_ms]);

    % 7. artefact rejection (see REJECT_MODE)
    switch reject_mode
      case 'abs'   % EEGLAB idiom: reject if |amplitude| exceeds the threshold anywhere
        EEG = pop_eegthresh(EEG, 1, 1:EEG.nbchan, -rej_thresh, rej_thresh, ...
                            ep(1), ep(2), 0, 1);
      case 'p2p'   % MNE's `reject=dict(eeg=...)` semantics: peak-to-peak within the epoch
        pp = squeeze(max(EEG.data, [], 2) - min(EEG.data, [], 2));   % nbchan x ntrials
        bad = find(any(pp > rej_thresh, 1));
        if ~isempty(bad); EEG = pop_rejepoch(EEG, bad, 0); end
      case 'none'
        % keep every epoch — both toolboxes then average the identical trial set
      otherwise
        error('unknown REJECT_MODE: %s', reject_mode);
    end

    % 8. split conditions by the *time-locking* event (latency 0), not the first event
    %    in the epoch — an epoch can contain several events.
    lab = cell(1, length(EEG.epoch));
    for e = 1:length(EEG.epoch)
      t = EEG.epoch(e).eventtype;  l = EEG.epoch(e).eventlatency;
      if ~iscell(t); t = {t}; end
      if ~iscell(l); l = {l}; end
      lat = zeros(1, length(l));
      for j = 1:length(l); lat(j) = abs(double(l{j})); end
      [~, j0] = min(lat);
      tj = t{j0}; if ~ischar(tj); tj = num2str(tj); end
      lab{e} = tj;
    end
    isa_ = strcmp(lab, 'A');  isb_ = strcmp(lab, 'B');

    if sum(isa_) < min_a || sum(isb_) < min_b
      printf('%s SKIP a=%d b=%d (need %d/%d)\n', sid, sum(isa_), sum(isb_), min_a, min_b);
      continue;
    end

    % 9. difference wave and ROI x window measurement
    dwave = mean(EEG.data(:,:,isa_), 3) - mean(EEG.data(:,:,isb_), 3);
    ridx = [];
    for c = 1:length(roi)
      k = find(strcmpi({EEG.chanlocs.labels}, roi{c}));
      if ~isempty(k); ridx(end+1) = k(1); end
    end
    tmask = EEG.times >= win(1) & EEG.times <= win(2);
    v = mean(mean(dwave(ridx, tmask)));

    subs{end+1} = sid; vals(end+1) = v; na(end+1) = sum(isa_); nb(end+1) = sum(isb_);
    printf('%s %s=%.4f uV (a=%d b=%d)\n', sid, comp, v, sum(isa_), sum(isb_));
  catch err
    printf('%s ERROR %s\n', sid, err.message);
  end
end

% ------------------------------------------------------------------------ write JSON
odir = fileparts(outfile);
if ~isempty(odir) && ~exist(odir, 'dir'); mkdir(odir); end
fid = fopen(outfile, 'w');
fprintf(fid, '{"component": "%s", "reject_mode": "%s", "toolbox": "EEGLAB/Octave",\n', comp, reject_mode);
fprintf(fid, ' "per_subject": {');
for k = 1:length(subs)
  if k > 1; fprintf(fid, ', '); end
  fprintf(fid, '"%s": %.4f', subs{k}, vals(k));
end
fprintf(fid, '},\n "n_trials": {');
for k = 1:length(subs)
  if k > 1; fprintf(fid, ', '); end
  fprintf(fid, '"%s": [%d, %d]', subs{k}, na(k), nb(k));
end
fprintf(fid, '},\n "n_analyzed": %d, "grand_mean_uV": %.4f}\n', length(vals), mean(vals));
fclose(fid);
printf('DONE %s n=%d grand=%.4f uV -> %s\n', comp, length(vals), mean(vals), outfile);
