function columns = csemxStringColumns(tableName)
%CSEMXSTRINGCOLUMNS Core columns that must not be inferred as numeric.

switch char(tableName)
    case "tx"
        columns = ["tx_station_id", "tx_component_id", "geometry_type", "notes", "time_utc"];
    case "tx_vertices"
        columns = ["tx_station_id", "tx_component_id"];
    case "rx"
        columns = ["rx_station_id", "rx_component_id", "geometry_type", "notes", "time_utc"];
    case "rx_vertices"
        columns = ["rx_station_id", "rx_component_id"];
    case "data"
        columns = ["tx_station_id", "tx_component_id", "rx_station_id", "rx_component_id"];
    case "groups"
        columns = ["group_kind", "group_id", "element_kind", "station_id", "component_id", "notes"];
    otherwise
        columns = strings(1, 0);
end
end
