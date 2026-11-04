// Reads one CSV file from this project's published data branch on GitHub, with headers promoted and empty fields as null (all columns still text).
// Fixed base address + RelativePath, so the Power BI Service refreshes it with no gateway and no "dynamic data source" error.
(path as text) as table =>
let
    // Download the file; we check the status ourselves so a failure gives a plain-English message.
    // IsRetry = true ignores any copy Power Query cached earlier, so every refresh gets the pipeline's latest files.
    Reply = Web.Contents("https://raw.githubusercontent.com", [RelativePath = DataRepoPath & "/" & path, Timeout = #duration(0, 0, 5, 0), ManualStatusHandling = {404, 429, 500, 502, 503, 504}, IsRetry = true]),
    // The reply's status code (200 = success)
    Status = Value.Metadata(Reply)[Response.Status],
    // Stop the refresh with a clear message if GitHub did not return the file (a failed refresh keeps the last good data in the Service)
    Checked = if Status = 200 then Binary.Buffer(Reply) else error Error.Record("GitHub returned HTTP " & Text.From(Status), "GitHub returned HTTP " & Text.From(Status) & " for " & path & ". Check that the repository is public and the nightly run has published."),
    // Parse the CSV (UTF-8, quoted fields)
    Csv = Csv.Document(Checked, [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    // First row holds the column names
    Promoted = Table.PromoteHeaders(Csv, [PromoteAllScalars = true]),
    // An empty field means "no value": make it null so typing never turns it into 0 or an error
    Nulls = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, Table.ColumnNames(Promoted))
in
    Nulls
