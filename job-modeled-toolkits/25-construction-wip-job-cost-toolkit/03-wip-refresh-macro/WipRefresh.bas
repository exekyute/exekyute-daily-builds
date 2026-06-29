Attribute VB_Name = "WipRefresh"
Option Explicit

' Sorts the WIP Schedule sheet built by the workbook tool, in place, by a column
' the user chooses, then reports the count of jobs in each billing position.
'
' The calculation logic stays out of the sub that touches cells: SortColumnFor
' maps a user's choice to a column letter and is the only place the valid keys
' live, and DataLastRow finds the last job row. The sub reads the choice,
' validates it, sorts, and shows the result.
'
' This tool sorts and reports. It never recomputes a number. The to-the-cent
' figures are produced and checked by the Python engine and verifier in 01 and
' 02, which run outside Excel and agree to the cent.

Private Const SCHEDULE_SHEET As String = "WIP Schedule"
Private Const FIRST_DATA_ROW As Long = 2
Private Const STATUS_COLUMN As String = "M"

' Map a sort choice to the schedule column it sorts on. Returns an empty string
' for an unknown choice, which the caller treats as invalid input.
Private Function SortColumnFor(ByVal key As String) As String
    Select Case UCase$(Trim$(key))
        Case "BILLING": SortColumnFor = "L"   ' over/under billing
        Case "EARNED": SortColumnFor = "H"    ' earned revenue
        Case "PROFIT": SortColumnFor = "K"    ' gross profit to date
        Case Else: SortColumnFor = ""
    End Select
End Function

' The last row that holds a job, found by walking down column A until the Total
' row or a blank cell. Returns a value below FIRST_DATA_ROW when there are none.
Private Function DataLastRow(ByVal ws As Worksheet) As Long
    Dim r As Long
    r = FIRST_DATA_ROW
    Do While ws.Cells(r, "A").Value <> "" And ws.Cells(r, "A").Value <> "Total"
        r = r + 1
    Loop
    DataLastRow = r - 1
End Function

Public Sub SortWipSchedule()
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(SCHEDULE_SHEET)
    On Error GoTo 0
    If ws Is Nothing Then
        MsgBox "No sheet named '" & SCHEDULE_SHEET & "' in this workbook.", _
               vbExclamation, "Sort WIP Schedule"
        Exit Sub
    End If

    Dim lastRow As Long
    lastRow = DataLastRow(ws)
    If lastRow < FIRST_DATA_ROW Then
        MsgBox "There are no job rows to sort.", vbExclamation, "Sort WIP Schedule"
        Exit Sub
    End If

    Dim choice As String
    choice = InputBox( _
        "Sort the WIP schedule by which column?" & vbNewLine & _
        "Enter BILLING, EARNED, or PROFIT.", "Sort WIP Schedule", "BILLING")
    If choice = "" Then Exit Sub   ' the user cancelled

    Dim sortColumn As String
    sortColumn = SortColumnFor(choice)
    If sortColumn = "" Then
        MsgBox "'" & choice & "' is not a sort key." & vbNewLine & _
               "Enter BILLING, EARNED, or PROFIT.", vbExclamation, "Sort WIP Schedule"
        Exit Sub
    End If

    Dim sortRange As Range
    Set sortRange = ws.Range("A" & FIRST_DATA_ROW & ":M" & lastRow)
    sortRange.Sort _
        Key1:=ws.Range(sortColumn & FIRST_DATA_ROW & ":" & sortColumn & lastRow), _
        Order1:=xlAscending, Header:=xlNo

    Dim r As Long, under As Long, over As Long, even As Long
    For r = FIRST_DATA_ROW To lastRow
        Select Case ws.Cells(r, STATUS_COLUMN).Value
            Case "Underbilled": under = under + 1
            Case "Overbilled": over = over + 1
            Case "Even": even = even + 1
        End Select
    Next r

    MsgBox "Sorted " & (lastRow - FIRST_DATA_ROW + 1) & " jobs by " & _
           UCase$(Trim$(choice)) & " (column " & sortColumn & ")." & vbNewLine & _
           "Underbilled: " & under & "   Overbilled: " & over & _
           "   Even: " & even, vbInformation, "Sort WIP Schedule"
End Sub
