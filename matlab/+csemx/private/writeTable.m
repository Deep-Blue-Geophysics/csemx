function writeTable(path, tableData, tableName)
%WRITETABLE Write a csemx CSV table with csemx missing-value semantics.

columns = string(tableData.Properties.VariableNames);
fid = fopen(path, "w", "n", "UTF-8");
if fid < 0
    error("csemx:WriteFailed", "Could not open file for writing: %s", path);
end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>

writeCsvRow(fid, columns);
for row = 1:height(tableData)
    values = strings(1, numel(columns));
    for col = 1:numel(columns)
        values(col) = formatCsvValue(tableData{row, col}, tableName, columns(col));
    end
    writeCsvRow(fid, values);
end
end

function writeCsvRow(fid, values)
escaped = arrayfun(@escapeCsvValue, values);
fprintf(fid, "%s\n", strjoin(escaped, ","));
end

function text = formatCsvValue(value, tableName, column)
if iscell(value)
    if isempty(value)
        text = "";
        return
    end
    value = value{1};
end

if isstring(value)
    if ismissing(value)
        text = "";
    else
        text = value;
    end
elseif ischar(value)
    text = string(value);
elseif isnumeric(value) || islogical(value)
    if isempty(value)
        text = "";
    elseif isscalar(value) && isnan(value)
        if tableName == "data" && any(column == ["real", "imag", "err_real", "err_imag"])
            text = "NaN";
        else
            text = "";
        end
    elseif isscalar(value)
        text = string(sprintf("%.17g", value));
    else
        text = string(mat2str(value));
    end
else
    text = string(value);
    if ismissing(text)
        text = "";
    end
end
end

function escaped = escapeCsvValue(value)
value = string(value);
if contains(value, """")
    value = replace(value, """", """""");
end
if contains(value, ",") || contains(value, newline) || contains(value, """")
    escaped = """" + value + """";
else
    escaped = value;
end
end
