function write(bundle, path, options)
%WRITE Write a MATLAB csemx struct as CSV tables.
%
%   csemx.write(BUNDLE, PATH) writes an unpacked bundle directory. If PATH ends
%   in .zip, a zipped csemx bundle is written with one top-level directory.

arguments
    bundle (1, 1) struct
    path (1, 1) string
    options.Overwrite (1, 1) logical = false
end

path = char(path);
isZip = endsWith(path, ".zip");

if isZip
    path = absolutePath(path);
    if isfile(path) && ~options.Overwrite
        error("csemx:FileExists", "File already exists: %s", path);
    end
    tmp = tempname;
    mkdir(tmp);
    cleanup = onCleanup(@() rmdir(tmp, "s")); %#ok<NASGU>
    [~, name, ext] = fileparts(path);
    root = fullfile(tmp, [name ext(1:end-4)]);
else
    root = path;
end

if isfolder(root)
    if ~options.Overwrite && ~isempty(dir(fullfile(root, "*")))
        error("csemx:DirectoryExists", "Directory already exists and is not empty: %s", root);
    end
    if options.Overwrite
        rmdir(root, "s");
    end
end
mkdir(root);

writeText(fullfile(root, "manifest.yaml"), bundle.manifest);
writeTable(fullfile(root, "tx.csv"), bundle.tx, "tx");
writeTable(fullfile(root, "tx_vertices.csv"), bundle.tx_vertices, "tx_vertices");
writeTable(fullfile(root, "rx.csv"), bundle.rx, "rx");
writeTable(fullfile(root, "rx_vertices.csv"), bundle.rx_vertices, "rx_vertices");
writeTable(fullfile(root, "data.csv"), bundle.data, "data");

if isfield(bundle, "notes") && strlength(string(bundle.notes)) > 0
    writeText(fullfile(root, "notes.md"), bundle.notes);
end

if isZip
    target = path;
    if isfile(target) && options.Overwrite
        delete(target);
    end
    here = pwd;
    finish = onCleanup(@() cd(here)); %#ok<NASGU>
    cd(tmp);
    [~, rootBase, rootExt] = fileparts(root);
    rootName = [rootBase rootExt];
    zip(target, rootName);
end
end
