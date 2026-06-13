function [root, cleanup] = resolveBundleRoot(path)
%RESOLVEBUNDLEROOT Resolve an unpacked bundle root, unpacking zip if needed.

path = char(path);
cleanup = [];

if endsWith(path, ".zip")
    tmp = tempname;
    mkdir(tmp);
    unzip(path, tmp);
    cleanup = onCleanup(@() rmdir(tmp, "s"));
    children = dir(tmp);
    children = children([children.isdir]);
    names = setdiff(string({children.name}), [".", ".."]);
    if numel(names) ~= 1
        error("csemx:InvalidBundle", "Zip bundle must contain one top-level directory");
    end
    root = fullfile(tmp, names(1));
    return
end

if isfile(fullfile(path, "manifest.yaml"))
    root = path;
    return
end

children = dir(path);
children = children([children.isdir]);
names = setdiff(string({children.name}), [".", ".."]);
if numel(names) == 1 && isfile(fullfile(path, names(1), "manifest.yaml"))
    root = fullfile(path, names(1));
    return
end

error("csemx:InvalidBundle", "Could not find manifest.yaml in bundle path");
end
