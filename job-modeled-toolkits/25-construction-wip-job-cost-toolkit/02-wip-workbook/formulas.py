"""The column layout and cell formulas for the WIP workbook.

One source of truth shared by two tools. build_workbook.py uses it to write the
formulas into the sheet; verify_workbook.py uses it to regenerate the expected
formula for every cell and confirm the workbook holds exactly that. Keeping the
formulas here, rather than inline in the builder, is what lets the verifier check
them without guessing.

The schedule sheet is laid out as columns A through M. Columns A to F hold the job
identifiers and the four input numbers as values. Columns G to M are live Excel
formulas that reference those inputs, so opening the workbook and editing any
input recomputes the row.
"""

# (column letter, engine CSV field, header, kind)
# kind is one of: text, input, formula.
COLUMNS = [
    ("A", "job_id", "Job ID", "text"),
    ("B", "job_name", "Job Name", "text"),
    ("C", "contract_value", "Contract Value", "input"),
    ("D", "estimated_total_cost", "Estimated Total Cost", "input"),
    ("E", "cost_to_date", "Cost to Date", "input"),
    ("F", "billed_to_date", "Billed to Date", "input"),
    ("G", "percent_complete", "Percent Complete", "formula"),
    ("H", "earned_revenue", "Earned Revenue", "formula"),
    ("I", "cost_to_complete", "Cost to Complete", "formula"),
    ("J", "estimated_gross_profit", "Est. Gross Profit", "formula"),
    ("K", "gross_profit_to_date", "Gross Profit to Date", "formula"),
    ("L", "over_under_billing", "Over/Under Billing", "formula"),
    ("M", "status", "Status", "formula"),
]

HEADER_ROW = 1
FIRST_DATA_ROW = 2

# Columns whose value is money, for number formatting and to-the-cent checks.
MONEY_COLUMNS = ["C", "D", "E", "F", "H", "I", "J", "K", "L"]
PERCENT_COLUMNS = ["G"]
TEXT_COLUMNS = ["A", "B", "M"]


def column_field(letter):
    for col, field, _header, _kind in COLUMNS:
        if col == letter:
            return field
    raise KeyError(letter)


def headers():
    return [header for _col, _field, header, _kind in COLUMNS]


def cell_formula(letter, row):
    """The live formula for a derived cell in a data row.

    Earned revenue and gross-profit columns reference the cost and contract input
    cells directly. The over/under and gross-profit-to-date columns reference the
    earned-revenue cell (H) so the chain matches how the engine computes them.
    """
    r = row
    formulas = {
        "G": "=ROUND(E{r}/D{r},4)".format(r=r),
        "H": "=ROUND(C{r}*E{r}/D{r},2)".format(r=r),
        "I": "=D{r}-E{r}".format(r=r),
        "J": "=C{r}-D{r}".format(r=r),
        "K": "=H{r}-E{r}".format(r=r),
        "L": "=H{r}-F{r}".format(r=r),
        "M": '=IF(L{r}>0,"Underbilled",IF(L{r}<0,"Overbilled","Even"))'.format(r=r),
    }
    return formulas[letter]


def total_formula(letter, first_row, last_row):
    """The formula for a column's cell in the totals row.

    Money columns sum their range. Percent complete is the cost-weighted aggregate,
    total cost to date over total estimated cost, not a sum of the row percentages.
    Text columns have no total.
    """
    if letter in ("A", "B", "M"):
        return None
    if letter == "G":
        return "=ROUND(SUM(E{first}:E{last})/SUM(D{first}:D{last}),4)".format(
            first=first_row, last=last_row
        )
    return "=SUM({col}{first}:{col}{last})".format(col=letter, first=first_row, last=last_row)


# Dashboard sheet: (label, formula, kind). Formulas reference the schedule sheet.
def dashboard_rows(first_row, last_row):
    sheet = "'WIP Schedule'"

    def rng(col):
        return "{s}!{c}{first}:{c}{last}".format(s=sheet, c=col, first=first_row, last=last_row)

    return [
        ("Total contract value", "=SUM(%s)" % rng("C"), "money"),
        ("Total estimated cost", "=SUM(%s)" % rng("D"), "money"),
        ("Total cost to date", "=SUM(%s)" % rng("E"), "money"),
        ("Total billed to date", "=SUM(%s)" % rng("F"), "money"),
        ("Total earned revenue", "=SUM(%s)" % rng("H"), "money"),
        ("Net over/under billing", "=SUM(%s)" % rng("L"), "money"),
        ("Gross profit to date", "=SUM(%s)" % rng("K"), "money"),
        ("Est. gross profit at completion", "=SUM(%s)" % rng("J"), "money"),
        ("Underbilled jobs", '=COUNTIF(%s,"Underbilled")' % rng("M"), "count"),
        ("Overbilled jobs", '=COUNTIF(%s,"Overbilled")' % rng("M"), "count"),
        ("Even jobs", '=COUNTIF(%s,"Even")' % rng("M"), "count"),
    ]
