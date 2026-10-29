% AEA_CLIENT_COMMAND - Build the native client's command, without running it.
% A Claude-compatible provider, including DeepSeek, is configured externally.
function [command, repository] = aea_client_command(project)
config = jsondecode(fileread(fullfile(project, 'AEA_BRIDGE_CONFIG.json')));
repository = config.repository;
executable = config.client_executable;
if isempty(executable), executable = config.client; end
prompt = ['Read and carry out the study request in ' fullfile(project, 'AEA_REQUEST.md') '.'];
if strcmp(config.client, 'codex')
    arguments = {executable, '--cd', repository, '--add-dir', project, prompt};
elseif strcmp(config.client, 'claude')
    arguments = {executable, '--add-dir', project, '--', prompt};
else
    error('AEA:Client', 'Choose codex or claude in AEA settings.');
end
quoted = cellfun(@aea_shell_quote, arguments, 'UniformOutput', false);
command = strjoin(quoted, ' ');
end
