function tableData = readTable(path, tableName)
%READTABLE Read a CSV or Parquet table.

path = char(path);
if endsWith(path, ".parquet")
    tableData = parquetread(path);
else
    opts = detectImportOptions(path, FileType="text", TextType="string");
    stringColumns = intersect(opts.VariableNames, csemxStringColumns(tableName));
    if ~isempty(stringColumns)
        opts = setvartype(opts, stringColumns, "string");
    end
    tableData = readtable(path, opts);
end
end
