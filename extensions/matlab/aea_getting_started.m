% AEA for MATLAB and EEGLAB
%
% Install this toolbox, then run aea_setup with the folder containing eeglab.m.
% If an AEA plugin is already installed, it is retained. Native MATLAB requires
% AEA plugin 0.1.3 or newer. Restart EEGLAB after a new plugin installation.
%
% Open Tools > AEA > Settings. Set the AEA checkout folder to the path returned
% by aea_library_root. Select backend matlab and leave Python blank. Enter the
% executable of a separately installed and signed-in Codex CLI or Claude Code.
%
% Export the current dataset to a new study directory and start AEA through
% the EEGLAB menu. Approve the study-specific plan before computation. The
% native helper supports explicit means from existing epochs, conditions,
% channels and a time window. It saves results, plots, HTML and replay code.
%
% The bundled library contains 22 skills and 10 recipes. MNE-Python remains
% the primary backend for the broader library. See resources/docs/MATLAB_NATIVE.md
% for native coverage and resources/docs/EEGLAB.md for the Python bridge.
%
% The repository and support tracker are at
% https://github.com/dengzhe-hou/auto-eeg-analysis
help aea_setup
disp(aea_library_root())
