function info = aea_setup(eeglab_root)
%AEA_SETUP Install the bundled adapter into an existing EEGLAB installation.
%   AEA_SETUP detects EEGLAB on the MATLAB path. AEA_SETUP(EEGLAB_ROOT)
%   uses an explicit installation folder. An existing AEA plugin is retained.
root = aea_library_root();
if nargin == 0
    entry = which('eeglab');
    if isempty(entry)
        error('AEA:EEGLABMissing', 'Add EEGLAB to the MATLAB path or supply its installation folder.');
    end
    eeglab_root = fileparts(entry);
end
if ~isfile(fullfile(eeglab_root, 'eeglab.m'))
    error('AEA:EEGLABMissing', 'The selected folder must contain eeglab.m.');
end
plugins = fullfile(eeglab_root, 'plugins');
existing = dir(fullfile(plugins, '*', 'eegplugin_aea.m'));
if numel(existing) > 1
    error('AEA:MultiplePlugins', 'Multiple AEA plugins exist. Keep one copy using the EEGLAB plugin manager.');
end
info = struct('library_root', root, 'plugin_folder', '', 'installed', false);
if ~isempty(existing)
    info.plugin_folder = existing(1).folder;
    fprintf('Existing AEA plugin retained at %s\n', info.plugin_folder);
    fprintf('For native MATLAB use AEA 0.1.3 or newer. Update older copies through EEGLAB.\n');
else
    destination = fullfile(plugins, 'aea0.1.3');
    if isfolder(destination) || isfile(destination)
        error('AEA:DestinationExists', 'The AEA destination already exists. No files were changed.');
    end
    if ~isfolder(plugins)
        mkdir(plugins);
    end
    copyfile(fullfile(root, 'extensions', 'eeglab', 'aea'), destination);
    copyfile(fullfile(root, 'LICENSE'), fullfile(destination, 'LICENSE'));
    info.plugin_folder = destination;
    info.installed = true;
    fprintf('AEA plugin installed at %s\n', destination);
end
fprintf('Restart EEGLAB and open Tools > AEA > Settings.\n');
fprintf('Set the AEA checkout folder to %s\n', root);
fprintf('Choose backend matlab for the native route and leave Python blank.\n');
fprintf('Configure your existing Codex or Claude executable in Settings.\n');
end
