function [L, NUM] = spm_bwlabel(BW, conn)
% Connected-component labelling, face-connectivity, pure Octave.
%
% WHY THIS EXISTS. FieldTrip's clusterstat/findcluster call spm_bwlabel to label contiguous
% supra-threshold regions. The SPM8 bundled with FieldTrip ships only compiled MATLAB MEX binaries
% (.mexa64 etc.) and a .m stub that errors; Octave cannot load those, so ft_timelockstatistics
% cannot run at all without a replacement.
%
% WHAT THIS MEANS FOR THE CERTIFICATION, stated plainly: with this file on the path, the FieldTrip
% arm is no longer 100% third-party code. What FieldTrip still contributes independently is
% everything that defines the test -- the t-statistic, the cluster-forming threshold, the maxsum
% cluster statistic, the permutation scheme, the null distribution and the p-value. What this file
% contributes is a standard connected-component labeller with no free parameters, verified against
% scipy.ndimage.label on random inputs by tools/tests/test_cluster_cert.py. It is a utility, not
% the statistic. The writeup says so.
%
% conn is SPM's face-connectivity code (6 for 3-D, and FieldTrip also passes 2*ndims).
% Only face connectivity is implemented, which is all either call site uses.

if nargin < 2, conn = 6; end
sz = size(BW);
if numel(sz) < 3, sz(end+1:3) = 1; end
BW = reshape(logical(BW), sz);
L = zeros(sz);
NUM = 0;

% Face-neighbour offsets only (no diagonals) -- this is what conn = 2*ndims means.
offs = [ 1 0 0; -1 0 0; 0 1 0; 0 -1 0; 0 0 1; 0 0 -1 ];

idx = find(BW);
if isempty(idx), return; end

for k = 1:numel(idx)
  if L(idx(k)) ~= 0, continue; end
  NUM = NUM + 1;
  stack = idx(k);
  L(idx(k)) = NUM;
  while ~isempty(stack)
    p = stack(end); stack(end) = [];
    [i, j, m] = ind2sub(sz, p);
    for o = 1:size(offs, 1)
      a = i + offs(o,1); b = j + offs(o,2); c = m + offs(o,3);
      if a < 1 || a > sz(1) || b < 1 || b > sz(2) || c < 1 || c > sz(3), continue; end
      q = sub2ind(sz, a, b, c);
      if BW(q) && L(q) == 0
        L(q) = NUM;
        stack(end+1) = q;   %#ok<AGROW>
      end
    end
  end
end
end
