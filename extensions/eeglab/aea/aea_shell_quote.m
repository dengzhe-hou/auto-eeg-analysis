% AEA_SHELL_QUOTE - Quote one path argument for MATLAB's system() shell.
function quoted = aea_shell_quote(value)
if ispc
    quoted = [char(34) value char(34)];
else
    q = char(39);
    escaped_quote = [q char(34) q char(34) q];
    quoted = [q strrep(value, q, escaped_quote) q];
end
end
