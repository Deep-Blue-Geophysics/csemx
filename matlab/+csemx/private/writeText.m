function writeText(path, text)
%WRITETEXT Write text as UTF-8.

fid = fopen(path, "w", "n", "UTF-8");
if fid < 0
    error("csemx:WriteFailed", "Could not open file for writing: %s", path);
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, "%s", text);
end
