% AEA_LAUNCH_MATLAB - Open a coding client from MATLAB without Python.
function info = aea_launch_matlab(project)
if ~exist(fullfile(project, 'AEA_HANDOFF.json'), 'file')
    error('AEA:NotPrepared', 'Prepare the exported study before starting AEA.');
end
[command, repository] = aea_client_command(project);
if ispc
    script = fullfile(project, 'start_aea.cmd');
    text = sprintf('@echo off\r\nsetlocal\r\nif "%%TERM%%"=="dumb" set "TERM="\r\ncd /d %s\r\ncall %s\r\n', ...
        aea_shell_quote(repository), command);
    launch = ['start "" cmd /k ' aea_shell_quote(script)];
else
    script = fullfile(project, 'start_aea.command');
    text = sprintf('#!/bin/bash\ncd %s || exit $?\nexec %s\n', aea_shell_quote(repository), command);
    if ismac
        launch = ['open -a Terminal ' aea_shell_quote(script)];
    else
        if isempty(getenv('DISPLAY')) && isempty(getenv('WAYLAND_DISPLAY'))
            error('AEA:NoTerminal', 'No desktop terminal. Start the client from %s with:\n%s', repository, command);
        end
        [found, ~] = system('command -v x-terminal-emulator');
        if found == 0
            launch = ['x-terminal-emulator -e bash ' aea_shell_quote(script) ' >/dev/null 2>&1 &'];
        else
            [found, ~] = system('command -v gnome-terminal');
            if found ~= 0, error('AEA:NoTerminal', 'No desktop terminal. Run:\n%s', command); end
            launch = ['gnome-terminal -- bash ' aea_shell_quote(script) ' >/dev/null 2>&1 &'];
        end
    end
end
fid = fopen(script, 'w', 'n', 'UTF-8');
if fid < 0, error('AEA:WriteFailed', 'Cannot write %s', script); end
fprintf(fid, '%s', text); fclose(fid);
if ismac
    [status, output] = system(['chmod +x ' aea_shell_quote(script)]);
    if status ~= 0, error('AEA:Launch', '%s', output); end
end
[status, output] = system(launch);
if status ~= 0, error('AEA:Launch', '%s', output); end
info = struct('status', 'terminal_open_requested', 'project', project, 'script', script);
end
