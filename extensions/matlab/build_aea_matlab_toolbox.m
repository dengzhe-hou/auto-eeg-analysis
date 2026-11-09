function output = build_aea_matlab_toolbox(source_root, output_root, manifest)
%BUILD_AEA_MATLAB_TOOLBOX Package the shared AEA library and MATLAB adapter.
if nargin < 3
    manifest = fullfile(source_root, 'packaging', 'RESOURCE_FILES.txt');
end
if isfolder(output_root) || isfile(output_root)
    error('AEA:OutputExists', 'Use a new output directory to preserve earlier build evidence.');
end
mkdir(output_root);
package_root = fullfile(output_root, 'toolbox-source');
mkdir(package_root);
resource_root = fullfile(package_root, 'resources');
mkdir(resource_root);
names = readlines(manifest);
names = names(strlength(names) > 0);
for index = 1:numel(names)
    source = fullfile(source_root, names(index));
    target = fullfile(resource_root, names(index));
    if ~isfolder(fileparts(target))
        mkdir(fileparts(target));
    end
    copyfile(source, target);
end
wrapper_root = fileparts(mfilename('fullpath'));
wrappers = {'aea_library_root.m', 'aea_setup.m', 'aea_getting_started.m', 'README.md'};
for index = 1:numel(wrappers)
    copyfile(fullfile(wrapper_root, wrappers{index}), package_root);
end
copyfile(fullfile(source_root, 'LICENSE'), fullfile(package_root, 'LICENSE'));
identity = jsondecode(fileread(fullfile(wrapper_root, 'toolbox-identity.json')));
options = matlab.addons.toolbox.ToolboxOptions(package_root, identity.identifier);
options.ToolboxName = 'AEA for MATLAB and EEGLAB';
options.ToolboxVersion = '0.1.3';
options.AuthorName = 'Dengzhe Hou';
options.Summary = 'EEGLAB data handoff and explicit epoched ERP means for coding agents.';
options.Description = fileread(fullfile(wrapper_root, 'README.md'));
options.ToolboxMatlabPath = string(package_root);
options.ToolboxGettingStartedGuide = fullfile(package_root, 'aea_getting_started.m');
options.MinimumMatlabRelease = 'R2026a';
options.MaximumMatlabRelease = '';
options.SupportedPlatforms.MatlabOnline = false;
options.OutputFile = fullfile(output_root, 'AEA_MATLAB_EEGLAB_0_1_3_preview.mltbx');
matlab.addons.toolbox.packageToolbox(options);
output = struct('package_file', char(options.OutputFile), ...
    'package_root', package_root, 'identifier', identity.identifier, ...
    'version', char(options.ToolboxVersion), 'matlab_version', version, ...
    'resource_count', numel(names), 'source_commit', ...
    'cdc0c30105cc4547aed8e5ece41739a8462cb47a');
fid = fopen(fullfile(output_root, 'BUILD_RESULT.json'), 'w');
cleanup = onCleanup(@()fclose(fid));
fprintf(fid, '%s\n', jsonencode(output, PrettyPrint=true));
end
