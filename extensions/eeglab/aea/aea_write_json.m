% AEA_WRITE_JSON - Write a UTF-8 study-sidecar file.
function aea_write_json(path, value)
fid = fopen(path, 'w', 'n', 'UTF-8');
if fid < 0, error('AEA:WriteFailed', 'Cannot write %s', path); end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '%s\n', jsonencode(value));
end
