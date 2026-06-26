"""Edge-case scenario definitions for the Benefit Engine.

This file is data, not logic. Each scenario describes one situation worth testing,
the inputs that produce it, and a short rationale explaining why it matters. The
generator in generate_cases.py runs each one through the engine and records the
result. Keeping the scenarios here means a reviewer can read the QA coverage at a
glance and add a case without touching the generator.

A scenario shaped as `expect_error: True` is one the engine must reject. The other
scenarios are expected to calculate cleanly.
"""

SCENARIOS = [
    {
        "name": "Normal retirement at 65",
        "rationale": "Baseline case: retiring at normal age means no reduction.",
        "salaries": ["100000", "100000", "100000", "100000", "100000"],
        "years_of_service": 30,
        "retirement_age": 65,
        "expect_error": False,
    },
    {
        "name": "Early retirement at 55",
        "rationale": "Ten years early at 6 percent per year is the maximum 60 percent reduction.",
        "salaries": ["100000", "100000", "100000", "100000", "100000"],
        "years_of_service": 30,
        "retirement_age": 55,
        "expect_error": False,
    },
    {
        "name": "Service above the cap",
        "rationale": "40 years of service must be clamped to the plan maximum of 35.",
        "salaries": ["90000", "92000", "94000", "96000", "98000"],
        "years_of_service": 40,
        "retirement_age": 65,
        "expect_error": False,
    },
    {
        "name": "Best 5 of many years",
        "rationale": "Only the five highest salaries should feed final average earnings.",
        "salaries": ["60000", "70000", "80000", "90000", "100000", "110000", "120000"],
        "years_of_service": 25,
        "retirement_age": 62,
        "expect_error": False,
    },
    {
        "name": "Boundary age just below normal",
        "rationale": "Retiring one year early should apply exactly one year of reduction.",
        "salaries": ["85000", "85000", "85000", "85000", "85000"],
        "years_of_service": 20,
        "retirement_age": 64,
        "expect_error": False,
    },
    {
        "name": "Invalid: negative salary rejected",
        "rationale": "A negative salary is never valid and must be rejected, not calculated.",
        "salaries": ["80000", "-5", "81000", "82000", "83000"],
        "years_of_service": 20,
        "retirement_age": 65,
        "expect_error": True,
    },
    {
        "name": "Invalid: age below earliest rejected",
        "rationale": "Retiring before the earliest allowed age must be rejected.",
        "salaries": ["80000", "81000", "82000", "83000", "84000"],
        "years_of_service": 20,
        "retirement_age": 50,
        "expect_error": True,
    },
]
