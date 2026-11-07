function root = aea_library_root()
%AEA_LIBRARY_ROOT Return the AEA resource folder supplied by the toolbox.
root = fullfile(fileparts(mfilename('fullpath')), 'resources');
if ~isfile(fullfile(root, 'AGENT_GUIDE.md'))
    error('AEA:ResourcesMissing', 'Install the built AEA toolbox before calling this function.');
end
end
