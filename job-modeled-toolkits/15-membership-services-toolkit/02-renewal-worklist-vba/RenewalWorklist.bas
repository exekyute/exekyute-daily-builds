Attribute VB_Name = "RenewalWorklist"
Option Explicit

' Builds the renewal worklist in Excel from the CSV the SQL tool writes
' (renewal_worklist.csv). It lays out and color-flags every record (expiring,
' lapsed, paid, and the records that need review), then writes the dues, HST,
' late-fee, and grand totals. Those totals match the SQL tool to the cent.
'
' Calculation logic lives in modCalc. The subs below only read the CSV and
' write cells, the same split between logic and plumbing the other tools use.

Private Const BILLABLE As String = "Paid,Expiring,Lapsed"

' Column positions in renewal_worklist.csv (1-based once split).
Private Const COL_ID As Integer = 1
Private Const COL_NAME As Integer = 2
Private Const COL_TIER As Integer = 3
Private Const COL_STATUS As Integer = 4
Private Const COL_EXPIRY As Integer = 5
Private Const COL_DUES As Integer = 6
Private Const COL_LATE As Integer = 7
Private Const COL_HST As Integer = 8
Private Const COL_TOTAL As Integer = 9
Private Const COL_ACTION As Integer = 10


' Main entry point. Pick renewal_worklist.csv when prompted.
Public Sub BuildRenewalWorklist()
    Dim csvPath As Variant
    csvPath = Application.GetOpenFilename( _
        "CSV files (*.csv),*.csv", , "Select renewal_worklist.csv")
    If csvPath = False Then Exit Sub

    Dim ws As Worksheet
    Set ws = SheetNamed("Worklist")
    ws.Cells.Clear

    ' Header row.
    Dim headers As Variant
    headers = Array("Member ID", "Name", "Tier", "Status", "Expiry", _
                    "Dues", "Late fee", "HST", "Total", "Action")
    Dim c As Integer
    For c = 0 To UBound(headers)
        ws.Cells(1, c + 1).Value = headers(c)
    Next c
    ws.Rows(1).Font.Bold = True

    Dim totalDues As Double, totalLate As Double
    Dim billableCount As Long, incompleteCount As Long
    Dim outRow As Long
    outRow = 2

    Dim fileNum As Integer, lineText As String, parts() As String
    Dim firstLine As Boolean
    firstLine = True

    fileNum = FreeFile
    Open csvPath For Input As #fileNum
    Do While Not EOF(fileNum)
        Line Input #fileNum, lineText
        If Len(Trim$(lineText)) = 0 Then GoTo ContinueLoop
        If firstLine Then
            firstLine = False          ' skip the CSV header row
            GoTo ContinueLoop
        End If

        parts = Split(lineText, ",")
        If UBound(parts) < COL_ACTION - 1 Then GoTo ContinueLoop

        Dim status As String, tier As String, duesText As String
        status = parts(COL_STATUS - 1)
        tier = parts(COL_TIER - 1)
        duesText = parts(COL_DUES - 1)

        ' Write the visible row.
        ws.Cells(outRow, COL_ID).Value = parts(COL_ID - 1)
        ws.Cells(outRow, COL_NAME).Value = parts(COL_NAME - 1)
        ws.Cells(outRow, COL_TIER).Value = tier
        ws.Cells(outRow, COL_STATUS).Value = status
        ws.Cells(outRow, COL_EXPIRY).Value = parts(COL_EXPIRY - 1)
        If Len(duesText) > 0 Then
            ws.Cells(outRow, COL_DUES).Value = CDbl(duesText)
            ws.Cells(outRow, COL_LATE).Value = CDbl(parts(COL_LATE - 1))
            ws.Cells(outRow, COL_HST).Value = CDbl(parts(COL_HST - 1))
            ws.Cells(outRow, COL_TOTAL).Value = CDbl(parts(COL_TOTAL - 1))
        End If
        ws.Cells(outRow, COL_ACTION).Value = parts(COL_ACTION - 1)

        FlagRow ws, outRow, status, tier

        ' Accumulate the billable totals (the manager's summary).
        If IsBillable(status) Then
            If Len(duesText) = 0 Then
                incompleteCount = incompleteCount + 1
            Else
                totalDues = totalDues + CDbl(duesText)
                totalLate = totalLate + CDbl(parts(COL_LATE - 1))
                billableCount = billableCount + 1
            End If
        End If

        outRow = outRow + 1
ContinueLoop:
    Loop
    Close #fileNum

    WriteSummary ws, outRow + 1, billableCount, incompleteCount, totalDues, totalLate
    ws.Columns.AutoFit

    Dim msg As String
    msg = "Worklist built." & vbNewLine & _
          billableCount & " billable members, total dues " & _
          Format$(totalDues, "#,##0.00") & "."
    If incompleteCount > 0 Then
        msg = msg & vbNewLine & incompleteCount & _
              " record(s) need review (missing tier or dues)."
    End If
    MsgBox msg, vbInformation, "Renewal worklist"
End Sub


' Writes the dues, HST, late-fee, and grand totals below the worklist.
Private Sub WriteSummary(ByVal ws As Worksheet, ByVal startRow As Long, _
                         ByVal members As Long, ByVal incomplete As Long, _
                         ByVal totalDues As Double, ByVal totalLate As Double)
    Dim totalHst As Double, grand As Double
    totalHst = HstOnDues(totalDues)
    grand = GrandTotalBilled(totalDues, totalHst, totalLate)

    ws.Cells(startRow, 1).Value = "Dues summary"
    ws.Cells(startRow, 1).Font.Bold = True
    ws.Cells(startRow + 1, 1).Value = "Billable members"
    ws.Cells(startRow + 1, 2).Value = members
    ws.Cells(startRow + 2, 1).Value = "Total dues"
    ws.Cells(startRow + 2, 2).Value = Format$(totalDues, "#,##0.00")
    ws.Cells(startRow + 3, 1).Value = "HST (13% on dues)"
    ws.Cells(startRow + 3, 2).Value = Format$(totalHst, "#,##0.00")
    ws.Cells(startRow + 4, 1).Value = "Late fees"
    ws.Cells(startRow + 4, 2).Value = Format$(totalLate, "#,##0.00")
    ws.Cells(startRow + 5, 1).Value = "Grand total billed"
    ws.Cells(startRow + 5, 2).Value = Format$(grand, "#,##0.00")
    ws.Cells(startRow + 5, 1).Font.Bold = True
    ws.Cells(startRow + 5, 2).Font.Bold = True
    If incomplete > 0 Then
        ws.Cells(startRow + 7, 1).Value = "Records needing review: " & incomplete
    End If
End Sub


' Color-flags a worklist row by status. Incomplete records (missing tier) are
' marked for review regardless of status.
Private Sub FlagRow(ByVal ws As Worksheet, ByVal r As Long, _
                    ByVal status As String, ByVal tier As String)
    Dim color As Long
    If Len(tier) = 0 Then
        color = RGB(255, 224, 178)        ' review: incomplete record
    ElseIf status = "Expiring" Then
        color = RGB(255, 242, 204)        ' expiring soon
    ElseIf status = "Lapsed" Then
        color = RGB(248, 203, 203)        ' lapsed
    ElseIf status = "Paid" Then
        color = RGB(214, 234, 214)        ' paid / current
    ElseIf status = "Duplicate" Then
        color = RGB(217, 217, 217)        ' duplicate, review
    Else
        color = RGB(255, 255, 255)
    End If
    ws.Range(ws.Cells(r, COL_ID), ws.Cells(r, COL_ACTION)).Interior.color = color
End Sub


Private Function IsBillable(ByVal status As String) As Boolean
    IsBillable = (InStr(1, "," & BILLABLE & ",", "," & status & ",") > 0)
End Function


' Returns the named sheet, creating it if it is not there yet.
Private Function SheetNamed(ByVal sheetName As String) As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(sheetName)
    On Error GoTo 0
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Worksheets.Add
        ws.Name = sheetName
    End If
    Set SheetNamed = ws
End Function


' In-Excel check of the calculation logic against the hand-checked figures in
' spec.md. Run it from the Macro dialog to screenshot a passing check.
Public Sub CalcSelfTest()
    Dim msg As String, ok As Boolean
    ok = True

    ok = ok And Assert("ProratedDues Associate/4", ProratedDues("Associate", 4), 112.5, msg)
    ok = ok And Assert("ProratedDues Student/12", ProratedDues("Student", 12), 6.25, msg)
    ok = ok And Assert("ProratedDues Professional/1", ProratedDues("Professional", 1), 300#, msg)
    ok = ok And Assert("HST on 1733.75", HstOnDues(1733.75), 225.39, msg)
    ok = ok And Assert("Grand total", GrandTotalBilled(1733.75, 225.39, 25#), 1984.14, msg)

    msg = msg & vbNewLine & IIf(ok, "All checks passed.", "Some checks FAILED.")
    MsgBox msg, IIf(ok, vbInformation, vbExclamation), "Calculation self-test"
End Sub


Private Function Assert(ByVal label As String, ByVal got As Double, _
                        ByVal want As Double, ByRef log As String) As Boolean
    Dim passed As Boolean
    passed = (Abs(got - want) < 0.005)
    log = log & IIf(passed, "[PASS] ", "[FAIL] ") & label & _
          ": got " & Format$(got, "#,##0.00") & _
          ", expected " & Format$(want, "#,##0.00") & vbNewLine
    Assert = passed
End Function
