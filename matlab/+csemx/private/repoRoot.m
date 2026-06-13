function root = repoRoot()
%REPOROOT Return the repository root for checkout-local MATLAB helpers.

thisFile = mfilename("fullpath");
root = fileparts(fileparts(fileparts(fileparts(thisFile))));
end
