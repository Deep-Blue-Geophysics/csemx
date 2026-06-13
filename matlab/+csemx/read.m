function bundle = read(path)
%READ Read an unpacked or zipped csemx bundle into a MATLAB struct.
%
%   BUNDLE = csemx.read(PATH) loads manifest.yaml as text, tables as MATLAB
%   tables, and notes.md as text when present.

arguments
    path (1, 1) string
end

[root, cleanup] = resolveBundleRoot(path); %#ok<ASGLU>

bundle = struct();
bundle.path = path;
bundle.manifest = fileread(fullfile(root, "manifest.yaml"));
bundle.tx = readTable(tablePath(root, "tx"), "tx");
bundle.tx_vertices = readTable(tablePath(root, "tx_vertices"), "tx_vertices");
bundle.rx = readTable(tablePath(root, "rx"), "rx");
bundle.rx_vertices = readTable(tablePath(root, "rx_vertices"), "rx_vertices");
bundle.data = readTable(tablePath(root, "data"), "data");

notesPath = fullfile(root, "notes.md");
if isfile(notesPath)
    bundle.notes = fileread(notesPath);
else
    bundle.notes = "";
end
end
