// One row per nightly run. Adds the run's number, marks the newest run, and turns its finish time into a real date and time.
let
    // Read the file from the data branch
    Source = fnRepoCsv("history/run_log.csv"),
    // Give every column its type. en-US means numbers use a dot, and dates are read as written, year first
    Typed = Table.TransformColumnTypes(Source, {{"run_id", type text}, {"as_of", type date}, {"started_utc", type text}, {"finished_utc", type text}, {"seconds", Int64.Type}, {"engine_version", type text}, {"register_rules", Int64.Type}, {"trigger", type text}, {"results_status", type text}, {"points_status", type text}, {"bathing_status", type text}, {"codes_status", type text}, {"watch_status", type text}, {"source_rows", Int64.Type}, {"loaded_rows", Int64.Type}, {"api_calls", Int64.Type}, {"rules_pass", Int64.Type}, {"rules_fail", Int64.Type}, {"rules_review", Int64.Type}, {"rules_not_checked", Int64.Type}, {"rules_no_data", Int64.Type}, {"planted_caught", Int64.Type}, {"planted_tested", Int64.Type}, {"verdict_monthly", type text}, {"verdict_trend", type text}, {"verdict_signoff", type text}, {"verdict_ai", type text}, {"tracking_since", type date}, {"github_run", type text}}, "en-US"),
    // Number the runs from 1, in the order they were written
    Numbered = Table.AddIndexColumn(Typed, "RunNo", 1, 1, Int64.Type),
    // How many runs there are
    Newest = Table.RowCount(Numbered),
    // Mark the newest run with a 1
    Marked = Table.AddColumn(Numbered, "IsLatest", each if [RunNo] = Newest then 1 else 0, Int64.Type),
    // The finish time as a date and time, leaving off the Z that marks it as UTC
    Timed = Table.AddColumn(Marked, "RunUTC", each DateTime.FromText(Text.Start([finished_utc], 19), "en-GB"), type datetime),
    // The same time in UK local time, as text such as "4 Nov 02:40". British Summer Time runs between the last Sundays of March and October, changing at 01:00 UTC
    Local = Table.AddColumn(Timed, "RunUKText", each
        let
            // The run's finish time
            U = [RunUTC],
            // That year's last Sunday in March
            Mar = Date.StartOfWeek(#date(Date.Year(U), 3, 31), Day.Sunday),
            // That year's last Sunday in October
            Oct = Date.StartOfWeek(#date(Date.Year(U), 10, 31), Day.Sunday),
            // Add an hour during British Summer Time
            L = U + #duration(0, if U >= (Mar & #time(1, 0, 0)) and U < (Oct & #time(1, 0, 0)) then 1 else 0, 0, 0)
        in
            // The day, short month and time
            Text.From(Date.Day(L)) & " " & Date.ToText(DateTime.Date(L), "MMM", "en-GB") & " " & DateTime.ToText(L, "HH:mm"), type text)
in
    Local
