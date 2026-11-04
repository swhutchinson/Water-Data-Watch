// The rule-by-month chart's data: one row per rule, with its history packed into text. Unrelated to any table, so picking a rule highlights its row instead of removing the others.
let
    // Read the file from the data branch
    Source = fnRepoCsv("rules_tonight.csv"),
    // Keep only what the chart draws
    Kept = Table.SelectColumns(Source, {"rule_order", "id", "title", "dimension", "severity", "status", "failed", "eligible", "failed_pct", "test_outcome", "effect_pct", "fix_rank", "owner_role", "why", "months_packed", "runs_packed"}),
    // Give every column its type. en-US means numbers use a dot
    Typed = Table.TransformColumnTypes(Kept, {{"rule_order", Int64.Type}, {"id", type text}, {"title", type text}, {"dimension", type text}, {"severity", type text}, {"status", type text}, {"failed", Int64.Type}, {"eligible", Int64.Type}, {"failed_pct", type number}, {"test_outcome", type text}, {"effect_pct", type number}, {"fix_rank", Int64.Type}, {"owner_role", type text}, {"why", type text}, {"months_packed", type text}, {"runs_packed", type text}}, "en-US")
in
    Typed
