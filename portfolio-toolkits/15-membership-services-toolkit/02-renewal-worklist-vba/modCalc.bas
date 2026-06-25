Attribute VB_Name = "modCalc"
Option Explicit

' Pure calculation functions for membership dues, HST, and the late fee.
' No worksheet access here. Each function takes values and returns a value, so
' the rules can be read and checked on their own, the same way the SQL runner
' keeps its query logic separate from its plumbing.
'
' These reproduce the figures the SQL tool prints:
'   ProratedDues("Associate", 4) = 112.50
'   ProratedDues("Student", 12)  = 6.25
'   HstOnDues(1733.75)           = 225.39

Public Const HST_RATE As Double = 0.13
Public Const LATE_FEE As Double = 25#
Public Const GRACE_DAYS As Long = 30

' Round half up to a number of decimal places. VBA's built-in Round uses
' banker's rounding (round half to even), so this helper is used everywhere to
' match the SQL and dashboard tools, which round half up.
Public Function RoundHalfUp(ByVal amount As Double, ByVal places As Integer) As Double
    Dim factor As Double
    factor = 10 ^ places
    RoundHalfUp = Int(amount * factor + 0.5) / factor
End Function

' Full-year dues for a tier. Raises an error for an unknown tier so a bad record
' is rejected with a clear message instead of being scored as zero.
Public Function AnnualDues(ByVal tier As String) As Double
    Select Case tier
        Case "Student": AnnualDues = 75#
        Case "Associate": AnnualDues = 150#
        Case "Professional": AnnualDues = 300#
        Case "Retired": AnnualDues = 90#
        Case Else
            Err.Raise vbObjectError + 513, "AnnualDues", _
                "Unknown membership tier: '" & tier & "'"
    End Select
End Function

' Dues for a member, prorated for the whole months remaining in the year,
' counting the join month. joinMonth is 1 to 12.
Public Function ProratedDues(ByVal tier As String, ByVal joinMonth As Integer) As Double
    If joinMonth < 1 Or joinMonth > 12 Then
        Err.Raise vbObjectError + 514, "ProratedDues", _
            "Join month must be 1 to 12, got " & joinMonth
    End If
    Dim monthsRemaining As Integer
    monthsRemaining = 13 - joinMonth
    ProratedDues = RoundHalfUp(AnnualDues(tier) * monthsRemaining / 12#, 2)
End Function

' HST charged on a dues amount. The late fee is not taxed.
Public Function HstOnDues(ByVal dues As Double) As Double
    HstOnDues = RoundHalfUp(dues * HST_RATE, 2)
End Function

' The grand total billed: dues plus HST plus late fees.
Public Function GrandTotalBilled(ByVal totalDues As Double, _
                                 ByVal totalHst As Double, _
                                 ByVal totalLate As Double) As Double
    GrandTotalBilled = totalDues + totalHst + totalLate
End Function
