// River figures worked out every way a person might. Each row is one finished figure, because medians can't be added up. Adds the sub-area's name in normal capitals.
let
    // Read the file from the data branch
    Source = fnRepoCsv("same_data.csv"),
    // Give every column its type. en-US means numbers use a dot
    Typed = Table.TransformColumnTypes(Source, {{"det_code", type text}, {"det_name", type text}, {"plain_name", type text}, {"sub_area", type text}, {"method", type text}, {"sample_set", type text}, {"month_set", type text}, {"statistic", type text}, {"figure", type number}, {"rows_used", Int64.Type}, {"rows_in_scope", Int64.Type}, {"is_ranked_area", type logical}, {"area_rank", Int64.Type}, {"scenario_key", type text}, {"unit_label", type text}}, "en-US"),
    // The sub-area's name in normal capitals, because the source holds it in capitals
    Named = Table.AddColumn(Typed, "area_name", each Text.Proper([sub_area]), type text)
in
    Named
