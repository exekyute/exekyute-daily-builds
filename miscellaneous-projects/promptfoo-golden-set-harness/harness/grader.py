"""promptfoo assertion entry point.

Wired into both config files as a single `defaultTest` assertion, so every case is
scored by the same rubric without repeating assertions 15 times in the golden set.

promptfoo records the returned score on each row. harness/report.py recomputes the
same score from the recorded response and checks the two agree, which is what makes
the report trustworthy rather than a second opinion.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scoring  # noqa: E402  (path has to be set before the import)


def get_assert(output, context):
    expected = (context.get("vars") or {}).get("expected") or {}
    if not expected:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "golden case is missing its expected values",
        }
    problems = scoring.validate_golden(expected)
    if problems:
        return {
            "pass": False,
            "score": 0.0,
            "reason": "golden case is malformed: "
            + "; ".join("%s %s" % pair for pair in problems),
        }
    result = scoring.score_case(expected, output)
    return {
        "pass": result["exact_match"],
        "score": result["field_score"],
        "reason": scoring.describe_misses(result),
    }
