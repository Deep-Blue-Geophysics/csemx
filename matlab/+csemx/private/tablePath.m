function path = tablePath(root, name)
%TABLEPATH Return the CSV or Parquet table path for NAME.

csvPath = fullfile(root, name + ".csv");
parquetPath = fullfile(root, name + ".parquet");

if isfile(csvPath) && isfile(parquetPath)
    error("csemx:InvalidBundle", "Both CSV and Parquet exist for table: %s", name);
elseif isfile(csvPath)
    path = csvPath;
elseif isfile(parquetPath)
    path = parquetPath;
else
    error("csemx:InvalidBundle", "Missing table: %s", name);
end
end
