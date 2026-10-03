% EEGLAB/Octave 独立实现:ERP CORE MMN,对齐 harmonized minimal 规格
more off;
addpath(genpath('/home/hou/eeglab/functions'));
addpath(genpath('/home/hou/eeglab/plugins'));
subs = {}; vals = [];
for i = 1:40
  sid = sprintf('sub-%03d', i);
  f = sprintf('/home/hou/mne_data/MNE-erpcoremmn2021-data/%s/eeg/%s_task-MMN_eeg.set', sid, sid);
  if ~exist(f, 'file'); continue; end
  try
    EEG = pop_loadset('filename', sprintf('%s_task-MMN_eeg.set', sid), ...
                      'filepath', sprintf('/home/hou/mne_data/MNE-erpcoremmn2021-data/%s/eeg/', sid));
    % 丢 EOG
    EEG = pop_select(EEG, 'nochannel', {'HEOG_left','HEOG_right','VEOG_lower'});
    % 带通 0.1-30 (EEGLAB 的 FIR)
    EEG = pop_eegfiltnew(EEG, 0.1, 30);
    % 重采样 256
    EEG = pop_resample(EEG, 256);
    % 平均参考
    EEG = pop_reref(EEG, []);
    % 分段 -0.2..0.5(事件类型 '70'/'80')
    EEG = pop_epoch(EEG, {'70','80'}, [-0.2 0.5]);
    EEG = pop_rmbase(EEG, [EEG.times(1) 0]);
    % 峰峰剔除 100uV
    EEG = pop_eegthresh(EEG, 1, 1:EEG.nbchan, -100, 100, -0.2, 0.5, 0, 1);
    % 分条件
    types = cell(1, length(EEG.epoch));
    for e = 1:length(EEG.epoch)
      t = EEG.epoch(e).eventtype; if iscell(t); t = t{1}; end
      types{e} = num2str(t);
    end
    isdev = strcmp(types, '70'); isstd = strcmp(types, '80');
    if sum(isdev) < 50 || sum(isstd) < 150; printf('%s SKIP dev=%d std=%d\n', sid, sum(isdev), sum(isstd)); continue; end
    dev = mean(EEG.data(:,:,isdev), 3); std_ = mean(EEG.data(:,:,isstd), 3);
    diff = dev - std_;
    % ROI Fz FCz Cz, 100-250ms
    roi = []; for c = {'Fz','FCz','Cz'}
      idx = find(strcmpi({EEG.chanlocs.labels}, c{1})); if ~isempty(idx); roi(end+1) = idx; end
    end
    tmask = EEG.times >= 100 & EEG.times <= 250;
    v = mean(mean(diff(roi, tmask)));
    subs{end+1} = sid; vals(end+1) = v;
    printf('%s MMN=%.4f uV (dev=%d std=%d)\n', sid, v, sum(isdev), sum(isstd));
  catch err
    printf('%s ERROR %s\n', sid, err.message);
  end
end
fid = fopen('/tmp/eeglab_bench/eeglab_mmn.json','w');
fprintf(fid, '{"per_subject": {');
for k = 1:length(subs)
  if k > 1; fprintf(fid, ', '); end
  fprintf(fid, '"%s": %.4f', subs{k}, vals(k));
end
fprintf(fid, '}, "n_analyzed": %d, "grand_mean_uV": %.4f}\n', length(vals), mean(vals));
fclose(fid);
printf('DONE n=%d grand=%.4f\n', length(vals), mean(vals));
