"""The audit questions, in the order the inspector is asked them.

This is the one place to edit the questionnaire. Add, remove, or reorder the
questions here and both the prompts and the log columns follow. Each question is
a small dictionary:

  key      the short name used in the log and in code
  prompt   the text shown to the inspector
  type     which validator runs: "choice", "date", "number", or "text"
  choices  only for "choice" questions: the allowed answers

The log line is written in this same order, with a timestamp added in front.
"""

QUESTIONS = [
    {
        "key": "site_code",
        "prompt": "Site code",
        "type": "choice",
        "choices": ["NORTH", "HARBOR", "RIDGE"],
    },
    {
        "key": "inspection_date",
        "prompt": "Inspection date (YYYY-MM-DD)",
        "type": "date",
    },
    {
        "key": "inspector",
        "prompt": "Inspector name",
        "type": "text",
    },
    {
        "key": "fuel_reading",
        "prompt": "Fuel tank reading in gallons (a non-negative number)",
        "type": "number",
    },
    {
        "key": "result",
        "prompt": "Inspection result",
        "type": "choice",
        "choices": ["PASS", "FAIL"],
    },
    {
        "key": "notes",
        "prompt": "Notes",
        "type": "text",
    },
]

# The order of columns in the log line that follows the timestamp.
LOG_COLUMNS = ["timestamp"] + [q["key"] for q in QUESTIONS]
