function path = absolutePath(path)
%ABSOLUTEPATH Convert a relative path to an absolute path.

path = char(path);
isWindowsAbsolute = ~isempty(regexp(path, "^[A-Za-z]:[\\/]", "once"));
if startsWith(path, filesep) || isWindowsAbsolute
    return
end

path = fullfile(pwd, path);
end
