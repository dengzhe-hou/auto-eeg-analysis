% FieldTrip side of the cluster-permutation certification.
%
% Loads the SAME per-subject difference waves and the SAME adjacency graph that the MNE side used
% (exported by tools/benchmark/export_cluster_input.py), so the comparison is about the clustering
% and permutation algorithm rather than about how each toolbox happens to define channel
% neighbours -- which would otherwise dominate and tell us nothing.
%
% Usage:
%   export OCTAVE_HOME=$HOME/miniconda3/envs/octave
%   FT_DIR=... INPUT=...mat OUTFILE=...json \
%     $OCTAVE_HOME/bin/octave-cli --no-gui --quiet tools/benchmark/cluster_cert_fieldtrip.m

more off;
ft_dir = getenv('FT_DIR'); if isempty(ft_dir); ft_dir = getenv('FIELDTRIP_PATH'); end
if isempty(ft_dir); error('set FT_DIR or FIELDTRIP_PATH'); end
addpath(ft_dir); ft_defaults;
% FieldTrip's clusterstat/findcluster need spm_bwlabel, and the bundled SPM8 ships only MATLAB MEX
% binaries that Octave cannot load. A pure-Octave replacement is prepended to the path; it is a
% standard connected-component labeller, verified against scipy.ndimage.label, and it is a utility
% rather than part of the statistic. See the shim's own header and CLUSTER_CERT.md.
addpath(fullfile(fileparts(mfilename('fullpath')), 'octave_shims'), '-begin');
addpath(genpath(fullfile(ft_dir, 'external', 'spm8')));
addpath(fullfile(fileparts(mfilename('fullpath')), 'octave_shims'), '-begin');

infile  = getenv('INPUT');   if isempty(infile);  error('set INPUT'); end
outfile = getenv('OUTFILE'); if isempty(outfile); error('set OUTFILE'); end
nperm = str2double(getenv('NPERM')); if isnan(nperm); nperm = 5000; end
tail = str2double(getenv('TAIL')); if isnan(tail); tail = -1; end   % P3b is +1

S = load(infile);
X = S.X;                      % chan x time x subject
times = S.times(:)';
labels = cellstr(S.labels);
A = double(S.adjacency);
[nchan, ntime, nsub] = size(X);
printf('loaded %s: %d chan x %d time x %d subj\n', S.component, nchan, ntime, nsub);

% Rebuild FieldTrip timelock structures from the exported arrays.
data = cell(1, nsub);
for s = 1:nsub
  d = [];
  d.label   = labels;
  d.time    = times;
  d.avg     = X(:,:,s);
  d.dimord  = 'chan_time';
  data{s} = d;
end

% Zero condition, so a one-sample test becomes the paired test FieldTrip expects.
zero = cell(1, nsub);
for s = 1:nsub
  z = data{s}; z.avg = zeros(nchan, ntime); zero{s} = z;
end

% The adjacency comes from the file, NOT from ft_prepare_neighbours.
neighbours = struct('label', {}, 'neighblabel', {});
for c = 1:nchan
  neighbours(c).label = labels{c};
  neighbours(c).neighblabel = labels(logical(A(c,:)));
end
printf('adjacency: %d undirected edges (from the exported graph)\n', sum(A(:))/2);

cfg = [];
cfg.method           = 'montecarlo';
cfg.statistic        = 'ft_statfun_depsamplesT';
cfg.correctm         = 'cluster';
% CLUSTERALPHA is the seventh instance in this project of a stated number that does not say what
% it means. MNE forms clusters at the TWO-TAILED critical value (t.ppf(0.975, df) = 2.093 here);
% FieldTrip's cfg.clusteralpha with cfg.tail=-1 is ONE-TAILED (t.ppf(0.05, df) = -1.729), i.e. 83%
% as strict, so more samples survive and clusters grow. Both are defensible readings of
% "alpha = 0.05"; they are not the same test.
ca = str2double(getenv('CLUSTERALPHA')); if isnan(ca); ca = 0.05; end
cfg.clusteralpha     = ca;
cfg.clusterstatistic = 'maxsum';
cfg.clustertail      = tail;
cfg.tail             = tail;
cfg.alpha            = 0.05;
cfg.numrandomization = nperm;
cfg.neighbours       = neighbours;
cfg.minnbchan        = 0;           % MNE does not require a minimum neighbour count
lat = getenv('LATENCY');   % 'tmin tmax' in seconds, exact sample times, to crop like the validation scripts
if isempty(lat); cfg.latency = 'all'; else; cfg.latency = str2num(lat); end %#ok<ST2NM>
cfg.design           = [1:nsub, 1:nsub; ones(1,nsub), 2*ones(1,nsub)];
cfg.uvar             = 1;
cfg.ivar             = 2;

stat = ft_timelockstatistics(cfg, data{:}, zero{:});

% Collect clusters on the tested tail
tsums = []; npts = []; pvals = [];
if tail == 1
  if isfield(stat, 'posclusters') && ~isempty(stat.posclusters)
    for k = 1:numel(stat.posclusters)
      tsums(end+1) = stat.posclusters(k).clusterstat;
      pvals(end+1) = stat.posclusters(k).prob;
      npts(end+1)  = sum(stat.posclusterslabelmat(:) == k);
    end
  end
  [~, ord] = sort(tsums, 'descend');
else
  if isfield(stat, 'negclusters') && ~isempty(stat.negclusters)
    for k = 1:numel(stat.negclusters)
      tsums(end+1) = stat.negclusters(k).clusterstat;
      pvals(end+1) = stat.negclusters(k).prob;
      npts(end+1)  = sum(stat.negclusterslabelmat(:) == k);
    end
  end
  [~, ord] = sort(tsums, 'ascend');
end

dumpf = getenv('DUMP');
if ~isempty(dumpf)
  % Elementwise evidence (contract B5): the JSON summaries cannot support a bit-identity claim.
  statmap = stat.stat;
  labelmat = zeros(size(statmap));
  if tail == 1 && isfield(stat, 'posclusterslabelmat'); labelmat = stat.posclusterslabelmat; end
  if tail == -1 && isfield(stat, 'negclusterslabelmat'); labelmat = stat.negclusterslabelmat; end
  save('-v7', dumpf, 'statmap', 'labelmat');
end

fid = fopen(outfile, 'w');
fprintf(fid, '{\n  "toolbox": "FieldTrip/Octave",\n  "component": "%s",\n', S.component);
ntime_out = size(stat.stat, 2);   % after cfg.latency cropping -- the dimension actually analysed
fprintf(fid, '  "n_subjects": %d, "n_channels": %d, "n_times": %d, "n_times_input": %d,\n', nsub, nchan, ntime_out, ntime);
fprintf(fid, '  "window_s": [%.9g, %.9g], "clusteralpha": %g, "threshold_convention": "one-tailed t quantile at clusteralpha (FieldTrip semantics)",\n', stat.time(1), stat.time(end), ca);
fprintf(fid, '  "n_permutations": %d, "tail": %d,\n', nperm, tail);
fprintf(fid, '  "n_clusters": %d,\n', numel(tsums));
fprintf(fid, '  "n_significant": %d,\n', sum(pvals < 0.05));
fprintf(fid, '  "clusters": [');
for i = 1:numel(ord)
  k = ord(i);
  if i > 1; fprintf(fid, ', '); end
  fprintf(fid, '\n    {"rank": %d, "t_sum": %.4f, "n_points": %d, "p": %.6f, "significant": %s}', ...
          i-1, tsums(k), npts(k), pvals(k), merge(pvals(k) < 0.05, 'true', 'false'));
end
fprintf(fid, '\n  ],\n');
fprintf(fid, '  "t_obs_checksum": %.6f,\n', sum(abs(stat.stat(:))));
fprintf(fid, '  "t_obs_min": %.6f\n}\n', min(stat.stat(:)));
fclose(fid);
printf('DONE %d clusters, %d significant -> %s\n', numel(tsums), sum(pvals < 0.05), outfile);
