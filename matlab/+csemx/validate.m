function [ok, output] = validate(path, options)
%VALIDATE Run the Python csemx validator from MATLAB.
%
%   OK = csemx.validate(PATH) returns true when the validator exits cleanly.
%   [OK, OUTPUT] also returns validator stdout/stderr text.

arguments
    path (1, 1) string
    options.Full (1, 1) logical = false
    options.Python (1, 1) string = "python3"
end

root = repoRoot();
validator = fullfile(root, "tools", "validate_csemx.py");

args = "";
if options.Full
    args = args + " --full";
end

command = sprintf('"%s" "%s"%s "%s"', options.Python, validator, args, path);
[status, output] = system(command);
ok = (status == 0);

if nargout == 0
    fprintf("%s", output);
    if ~ok
        error("csemx:ValidationFailed", "csemx validation failed");
    end
end
end
