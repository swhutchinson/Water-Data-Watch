// When the data was last refreshed, captured once per refresh: in UTC, and as UK local date and text (the Power BI Service runs in UTC, so the BST rule is written out here). Every "latest" or "updated" label counts from this, never from NOW().
let
    // The refresh time in UTC
    Now = DateTimeZone.RemoveZone(DateTimeZone.UtcNow()),
    // This year
    Y = Date.Year(Now),
    // Last Sunday in March and in October (start and end of British Summer Time)
    MarchSunday = Date.StartOfWeek(#date(Y, 3, 31), Day.Sunday),
    // Last Sunday in October
    OctoberSunday = Date.StartOfWeek(#date(Y, 10, 31), Day.Sunday),
    // BST runs from 01:00 UTC on the last Sunday in March to 01:00 UTC on the last Sunday in October
    IsBst = Now >= (MarchSunday & #time(1, 0, 0)) and Now < (OctoberSunday & #time(1, 0, 0)),
    // UK local time
    Local = Now + #duration(0, if IsBst then 1 else 0, 0, 0),
    // A one-row table: UTC, UK local date, and UK local text such as "26 Oct 18:42"
    Result = #table(type table [RefreshedUTC = datetime, RefreshedUKDate = date, RefreshedUKText = text],
        {{Now, DateTime.Date(Local), Text.From(Date.Day(Local)) & " " & Date.ToText(DateTime.Date(Local), "MMM", "en-GB") & " " & DateTime.ToText(Local, "HH:mm")}})
in
    Result
