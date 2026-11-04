# Times every visual's query from a cold cache against the model open in Power BI Desktop.
# Usage: powershell -File tools\cold_timings.ps1 -Port 60499 [-QueryFile build\fixture_queries.json]
# Takes the port of the Desktop model, and which file holds the queries
param([Parameter(Mandatory = $true)][int]$Port, [string]$QueryFile = 'build\fixture_queries.json')
# Finds the folder holding the Power BI client library
. 'C:\Projects\power-bi-studio\scripts\pbi_bin.ps1'
# Loads the library that talks to the model
Add-Type -Path (Join-Path $PbiBin 'Microsoft.PowerBI.AdomdClient.dll')
# Connects to the model
$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection "Data Source=localhost:$Port"
$conn.Open()
# Asks for the name of the model, which clearing the cache needs
$cmd = $conn.CreateCommand(); $cmd.CommandText = 'SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS'
$found = $cmd.ExecuteReader(); [void]$found.Read(); $db = $found.GetValue(0); $found.Close()
# Reads the queries, one for each visual
$queries = Get-Content $QueryFile -Raw | ConvertFrom-Json
# Runs each query in turn
foreach ($q in $queries.PSObject.Properties) {
    # Empties the cache, so this query starts cold
    $clear = $conn.CreateCommand()
    $clear.CommandText = "<ClearCache xmlns='http://schemas.microsoft.com/analysisservices/2003/engine'><Object><DatabaseID>$db</DatabaseID></Object></ClearCache>"
    [void]$clear.ExecuteNonQuery()
    # Starts the clock
    $watch = [Diagnostics.Stopwatch]::StartNew()
    # Runs the query and reads every row, as a visual would
    $run = $conn.CreateCommand(); $run.CommandText = $q.Value
    $reader = $run.ExecuteReader(); $count = 0
    while ($reader.Read()) { $count++ }
    $reader.Close()
    # Stops the clock
    $watch.Stop()
    # Reports the visual, its rows and its cold time
    '{0,-14} {1,6} rows {2,6} ms' -f $q.Name, $count, $watch.ElapsedMilliseconds
}
# Closes the connection
$conn.Close()
