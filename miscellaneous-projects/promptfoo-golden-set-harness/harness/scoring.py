"""Scoring rules for the freight-document golden set.

Pure functions only, standard library only, no file or network access. Both callers
share this module so the rubric has exactly one implementation: harness/grader.py
scores a single response while promptfoo is running, and harness/report.py rescores
every recorded response afterwards to build the accuracy, consistency, hallucination,
and regression tables.

The rubric in prose is golden/rubric.md. When the two disagree, this file is the one
that ran.
"""

import json
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SCHEMA_FIELDS = (
    "shipment_id",
    "carrier_scac",
    "container_id",
    "gross_weight_kg",
    "incoterm",
    "port_of_loading",
    "ship_date",
    "declared_value_usd",
    "hazmat",
)

INCOTERMS = frozenset(
    ("EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP")
)

# Text a model uses to say "this document does not state the value". Treated as an
# abstention, not as a wrong answer, because it carries the same meaning as null.
NULL_TOKENS = frozenset(
    (
        "",
        "null",
        "none",
        "nil",
        "n/a",
        "na",
        "not present",
        "not stated",
        "not specified",
        "not provided",
        "unknown",
        "unreadable",
        "-",
        "--",
    )
)

POUNDS_TO_KG = Decimal("0.45359237")
KG_PER_TONNE = Decimal("1000")

CONTAINER_PATTERN = re.compile(r"^[A-Z]{4}[0-9]{7}$")
SCAC_PATTERN = re.compile(r"^[A-Z]{2,4}$")
ISO_DATE_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
SLASH_DATE_PATTERN = re.compile(r"^(\d{1,4})[/-](\d{1,2})[/-](\d{2,4})$")


class _Invalid:
    """A value the model did produce that no rule can turn into a schema value.

    Distinct from None: None means the model abstained, which is the correct answer
    when the document is silent. _Invalid never compares equal to anything, so it
    always scores as a miss, and it still counts as a fabricated value when the
    golden answer is null.
    """

    def __repr__(self):
        return "INVALID"

    def __eq__(self, other):
        return False

    def __hash__(self):
        return hash("__invalid__")


INVALID = _Invalid()


def _text(value):
    """Collapse a value to trimmed single-spaced text, or None if it reads as absent."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    text = re.sub(r"\s+", " ", str(value)).strip()
    if text.lower() in NULL_TOKENS:
        return None
    return text


def _quantize(value, places):
    exponent = Decimal(1).scaleb(-places)
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def normalize_weight_kg(value):
    """Kilograms, rounded half up to one decimal.

    A bare number is taken as kilograms. A number carrying a unit is converted, so a
    model that answers "26455 lb" is scored on the weight it meant rather than on the
    unit it left in the string.
    """
    text = _text(value)
    if text is None:
        return None
    lowered = text.lower().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", lowered)
    if match is None:
        return INVALID
    try:
        amount = Decimal(match.group(0))
    except InvalidOperation:
        return INVALID
    if re.search(r"\b(lb|lbs|pound|pounds)\b", lowered):
        amount = amount * POUNDS_TO_KG
    elif re.search(r"\b(mt|tonne|tonnes|metric tons?)\b", lowered):
        amount = amount * KG_PER_TONNE
    if amount < 0:
        return INVALID
    return _quantize(amount, 1)


def normalize_money(value):
    """A USD amount, rounded half up to two decimals, symbols and separators removed."""
    text = _text(value)
    if text is None:
        return None
    stripped = re.sub(r"(?i)\b(usd|dollars?)\b", "", text)
    stripped = stripped.replace("$", "").replace(",", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", stripped)
    if match is None:
        return INVALID
    try:
        amount = Decimal(match.group(0))
    except InvalidOperation:
        return INVALID
    if amount < 0:
        return INVALID
    return _quantize(amount, 2)


def normalize_date(value):
    """An ISO 8601 calendar date.

    YYYY-MM-DD passes through. A day-first date passes when the first part is above
    12, which makes the reading unambiguous. A slash date that could be read either
    way is invalid rather than guessed, because guessing here silently swaps March 4
    for April 3.
    """
    text = _text(value)
    if text is None:
        return None
    text = text.split("T")[0].split(" ")[0]
    iso = ISO_DATE_PATTERN.match(text)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
        return _iso_or_invalid(year, month, day)
    slashed = SLASH_DATE_PATTERN.match(text)
    if slashed:
        first, second, third = (int(part) for part in slashed.groups())
        if first > 31 and third <= 31:
            return _iso_or_invalid(first, second, third)
        if first > 12 and third > 31:
            return _iso_or_invalid(third, second, first)
        return INVALID
    return INVALID


def _iso_or_invalid(year, month, day):
    if not 1 <= month <= 12:
        return INVALID
    if not 1 <= day <= 31:
        return INVALID
    if year < 1900 or year > 2999:
        return INVALID
    return "%04d-%02d-%02d" % (year, month, day)


def normalize_container(value):
    """An ISO 6346 container number, four letters then seven digits, nothing between."""
    text = _text(value)
    if text is None:
        return None
    compact = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    if CONTAINER_PATTERN.match(compact):
        return compact
    return INVALID


def normalize_scac(value):
    """A SCAC code, two to four letters. A carrier's name is not a SCAC."""
    text = _text(value)
    if text is None:
        return None
    compact = re.sub(r"[^A-Za-z]", "", text).upper()
    if SCAC_PATTERN.match(compact):
        return compact
    return INVALID


def normalize_incoterm(value):
    text = _text(value)
    if text is None:
        return None
    code = re.sub(r"[^A-Za-z]", "", text).upper()
    if code in INCOTERMS:
        return code
    return INVALID


def normalize_hazmat(value):
    text = _text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in ("true", "yes", "y", "1", "declared", "hazmat"):
        return True
    if lowered in ("false", "no", "n", "0", "none declared"):
        return False
    return INVALID


def normalize_code(value):
    """A port code or port name, uppercased, trailing punctuation dropped."""
    text = _text(value)
    if text is None:
        return None
    return text.upper().strip(" .,;:").replace("  ", " ")


def normalize_identifier(value):
    text = _text(value)
    if text is None:
        return None
    return text.upper()


NORMALIZERS = {
    "shipment_id": normalize_identifier,
    "carrier_scac": normalize_scac,
    "container_id": normalize_container,
    "gross_weight_kg": normalize_weight_kg,
    "incoterm": normalize_incoterm,
    "port_of_loading": normalize_code,
    "ship_date": normalize_date,
    "declared_value_usd": normalize_money,
    "hazmat": normalize_hazmat,
}


def normalize_field(name, value):
    """Normalize one field by name. Unknown field names fall back to plain text."""
    normalizer = NORMALIZERS.get(name, normalize_identifier)
    return normalizer(value)


def parse_output(raw):
    """Pull the JSON object out of a model response.

    Handles a bare object, an object wrapped in a fenced code block, and an object
    with commentary around it. Returns None when nothing parses, which the caller
    scores as a parse failure rather than as nine wrong fields.
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
    return parsed if isinstance(parsed, dict) else None


def score_case(expected, raw_output):
    """Score one response against one golden answer.

    Returns per-field detail plus the four numbers every table is built from: how many
    fields matched, whether the whole case was right, which fields were fabricated,
    and whether the response parsed at all.
    """
    parsed = parse_output(raw_output)
    fields = {}
    matched = 0
    hallucinated = []
    missing_keys = []

    for name in expected:
        want = normalize_field(name, expected[name])
        if parsed is None:
            got = None
            present = False
        else:
            present = name in parsed
            got = normalize_field(name, parsed.get(name)) if present else None
        if not present and parsed is not None:
            missing_keys.append(name)

        is_match = _values_equal(want, got)
        if is_match:
            matched += 1
        fabricated = want is None and got is not None and parsed is not None
        if fabricated:
            hallucinated.append(name)
        fields[name] = {
            "expected": want,
            "actual": got,
            "match": is_match,
            "expected_null": want is None,
            "hallucinated": fabricated,
            "present": present,
        }

    total = len(expected)
    return {
        "fields": fields,
        "matched": matched,
        "total": total,
        "field_score": (matched / total) if total else 0.0,
        "exact_match": bool(total) and matched == total,
        "hallucinated_fields": hallucinated,
        "missing_keys": missing_keys,
        "parse_error": parsed is None,
        "canonical": canonical_answer(expected, parsed),
    }


def _values_equal(want, got):
    if want is None and got is None:
        return True
    if want is None or got is None:
        return False
    if isinstance(want, _Invalid) or isinstance(got, _Invalid):
        return False
    return want == got


def canonical_answer(expected, parsed):
    """A stable string for the normalized answer, used to compare repeated runs.

    Consistency is measured on normalized values, so a model that reformats the same
    answer is not counted as unstable. Only a change in meaning shows up.
    """
    if parsed is None:
        return "PARSE_ERROR"
    parts = []
    for name in expected:
        value = normalize_field(name, parsed.get(name)) if name in parsed else None
        if value is None:
            rendered = "null"
        elif isinstance(value, _Invalid):
            rendered = "invalid"
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        parts.append("%s=%s" % (name, rendered))
    return "|".join(parts)


def validate_golden(expected):
    """Problems in a golden answer itself, as a list of (field, description).

    A golden value that no rule can normalize would mark every model wrong on that
    field and look like a model defect. The first version of this harness hit exactly
    that: the YAML loader read unquoted dates as date objects, every model "failed"
    ship_date, and the run reported 0 percent. The golden set is now checked before any
    response is scored, so that failure reports itself as a golden-set defect.
    """
    problems = []
    for name in expected:
        if name not in NORMALIZERS:
            problems.append((name, "not a field in the schema"))
            continue
        if isinstance(normalize_field(name, expected[name]), _Invalid):
            problems.append(
                (name, "golden value %r does not normalize" % (expected[name],))
            )
    return problems


def version_key(label):
    """Reduce a promptfoo prompt label to the short version key it starts with.

    promptfoo composes a file-backed prompt's label out of the label, the path, and
    the prompt text, so the raw label arrives as "v2: prompts/extract-v2.txt: You
    extract...". Only the leading token identifies the version, and a label that is
    already short passes through unchanged.
    """
    if label is None:
        return "unknown"
    return str(label).split(":")[0].strip() or "unknown"


def describe_misses(result, limit=4):
    """One line naming what a scored response got wrong, for a grader reason string."""
    if result["parse_error"]:
        return "response did not parse as a JSON object"
    misses = []
    for name, detail in result["fields"].items():
        if detail["match"]:
            continue
        if not detail["present"]:
            note = "omitted"
        elif detail["hallucinated"]:
            note = "fabricated %r over an absent value" % (detail["actual"],)
        else:
            note = "got %r, expected %r" % (detail["actual"], detail["expected"])
        misses.append("%s (%s)" % (name, note))
    summary = "%d/%d fields" % (result["matched"], result["total"])
    if not misses:
        return summary
    shown = misses[:limit]
    if len(misses) > limit:
        shown.append("and %d more" % (len(misses) - limit))
    return "%s; %s" % (summary, "; ".join(shown))


def modal_agreement(canonicals):
    """Share of repeated runs that landed on the most common answer.

    One run is trivially consistent, so a single-repeat eval reports 1.0 here. That is
    a property of the run, not a finding, which is why the report prints the repeat
    count beside this number.
    """
    if not canonicals:
        return 0.0
    counts = {}
    for value in canonicals:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.values()) / len(canonicals)


def case_verdict(scored_rows):
    """pass when every repeat was exactly right, fail when none were, else unstable."""
    if not scored_rows:
        return "missing"
    passes = sum(1 for row in scored_rows if row["exact_match"])
    if passes == len(scored_rows):
        return "pass"
    if passes == 0:
        return "fail"
    return "unstable"


def summarize_variant(rows_by_case):
    """Roll one model and prompt version up into the four headline metrics.

    rows_by_case maps case_id to the list of scored rows for that case, one per repeat.
    """
    matched = total = 0
    null_fields = fabricated_fields = 0
    exact = row_count = 0
    parse_errors = 0
    agreements = []
    unstable = []
    verdicts = {}

    for case_id in sorted(rows_by_case):
        rows = rows_by_case[case_id]
        for row in rows:
            matched += row["matched"]
            total += row["total"]
            row_count += 1
            exact += 1 if row["exact_match"] else 0
            parse_errors += 1 if row["parse_error"] else 0
            for detail in row["fields"].values():
                if detail["expected_null"]:
                    null_fields += 1
                    if detail["hallucinated"]:
                        fabricated_fields += 1
        agreement = modal_agreement([row["canonical"] for row in rows])
        agreements.append(agreement)
        if agreement < 1.0:
            unstable.append(case_id)
        verdicts[case_id] = case_verdict(rows)

    return {
        "cases": len(rows_by_case),
        "rows": row_count,
        "field_accuracy": (matched / total) if total else 0.0,
        "fields_matched": matched,
        "fields_total": total,
        "case_pass_rate": (exact / row_count) if row_count else 0.0,
        "cases_exact": exact,
        "hallucination_rate": (fabricated_fields / null_fields) if null_fields else 0.0,
        "fabricated_fields": fabricated_fields,
        "null_fields": null_fields,
        "consistency": (sum(agreements) / len(agreements)) if agreements else 0.0,
        "unstable_cases": unstable,
        "parse_errors": parse_errors,
        "verdicts": verdicts,
    }


def compare_versions(base_verdicts, new_verdicts):
    """Case-level movement between two prompt versions for one model.

    A case that stops passing is a regression, including one that becomes unstable:
    an answer that is right two runs out of three is not a passing case.
    """
    regressions, fixes = [], []
    for case_id in sorted(set(base_verdicts) | set(new_verdicts)):
        before = base_verdicts.get(case_id, "missing")
        after = new_verdicts.get(case_id, "missing")
        if before == "pass" and after in ("fail", "unstable"):
            regressions.append({"case_id": case_id, "before": before, "after": after})
        elif before in ("fail", "unstable") and after == "pass":
            fixes.append({"case_id": case_id, "before": before, "after": after})
    return {"regressions": regressions, "fixes": fixes}
