"""Tests for the rubric: normalization, case scoring, metrics, and regressions."""

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness")
)

import scoring  # noqa: E402


GOLDEN = {
    "shipment_id": "SHP-88213",
    "carrier_scac": "MRDU",
    "container_id": "MRDU4419078",
    "gross_weight_kg": 18420.0,
    "incoterm": "FOB",
    "port_of_loading": "CNSHA",
    "ship_date": "2026-02-11",
    "declared_value_usd": 42300.00,
    "hazmat": False,
}


def perfect(**overrides):
    answer = dict(GOLDEN)
    answer.update(overrides)
    return answer


class TestWeight(unittest.TestCase):
    def test_bare_number_is_kilograms(self):
        self.assertEqual(scoring.normalize_weight_kg(18420), Decimal("18420.0"))

    def test_pounds_are_converted(self):
        self.assertEqual(scoring.normalize_weight_kg("26,455 LB"), Decimal("11999.8"))

    def test_tonnes_are_converted(self):
        self.assertEqual(scoring.normalize_weight_kg("12.5 MT"), Decimal("12500.0"))

    def test_rounds_half_up_to_one_decimal(self):
        self.assertEqual(scoring.normalize_weight_kg("11999.75"), Decimal("11999.8"))

    def test_absent_weight_is_none(self):
        self.assertIsNone(scoring.normalize_weight_kg(None))
        self.assertIsNone(scoring.normalize_weight_kg("not stated"))

    def test_text_without_a_number_is_invalid(self):
        self.assertIs(scoring.normalize_weight_kg("heavy"), scoring.INVALID)

    def test_negative_weight_is_invalid(self):
        self.assertIs(scoring.normalize_weight_kg("-40 kg"), scoring.INVALID)


class TestMoney(unittest.TestCase):
    def test_symbol_and_separators_are_stripped(self):
        self.assertEqual(scoring.normalize_money("$18,450.00 USD"), Decimal("18450.00"))

    def test_bare_number_gets_two_decimals(self):
        self.assertEqual(scoring.normalize_money(42300), Decimal("42300.00"))

    def test_zero_is_a_value_not_an_absence(self):
        self.assertEqual(scoring.normalize_money(0), Decimal("0.00"))
        self.assertIsNotNone(scoring.normalize_money("USD 0.00"))

    def test_rounds_half_up_to_two_decimals(self):
        self.assertEqual(scoring.normalize_money("9875.605"), Decimal("9875.61"))


class TestDate(unittest.TestCase):
    def test_iso_passes_through(self):
        self.assertEqual(scoring.normalize_date("2026-02-11"), "2026-02-11")

    def test_timestamp_is_trimmed_to_the_date(self):
        self.assertEqual(scoring.normalize_date("2026-02-11T08:30:00Z"), "2026-02-11")

    def test_unambiguous_day_first_is_accepted(self):
        self.assertEqual(scoring.normalize_date("14/03/2026"), "2026-03-14")

    def test_ambiguous_slash_date_is_invalid_rather_than_guessed(self):
        self.assertIs(scoring.normalize_date("03/04/2026"), scoring.INVALID)

    def test_impossible_month_is_invalid(self):
        self.assertIs(scoring.normalize_date("2026-13-01"), scoring.INVALID)

    def test_absent_date_is_none(self):
        self.assertIsNone(scoring.normalize_date("N/A"))


class TestCodesAndFlags(unittest.TestCase):
    def test_container_spacing_and_case_are_normalized(self):
        self.assertEqual(scoring.normalize_container("mrdu 765432-1"), "MRDU7654321")

    def test_container_of_the_wrong_shape_is_invalid(self):
        self.assertIs(scoring.normalize_container("####U 8?9##2"), scoring.INVALID)

    def test_scac_accepts_two_to_four_letters(self):
        self.assertEqual(scoring.normalize_scac("mrdu"), "MRDU")

    def test_carrier_name_is_not_a_scac(self):
        self.assertIs(scoring.normalize_scac("NORTHGATE CONTAINER LINE"), scoring.INVALID)

    def test_incoterm_must_be_in_the_published_set(self):
        self.assertEqual(scoring.normalize_incoterm("fob"), "FOB")
        self.assertIs(scoring.normalize_incoterm("FOBB"), scoring.INVALID)

    def test_hazmat_accepts_the_common_spellings(self):
        self.assertTrue(scoring.normalize_hazmat("Yes"))
        self.assertFalse(scoring.normalize_hazmat(0))
        self.assertIs(scoring.normalize_hazmat("maybe"), scoring.INVALID)

    def test_null_tokens_all_read_as_abstention(self):
        for token in ("", "null", "N/A", "not present", "unknown", "-"):
            self.assertIsNone(scoring.normalize_code(token), token)


class TestParseOutput(unittest.TestCase):
    def test_plain_json_object(self):
        self.assertEqual(scoring.parse_output('{"a": 1}'), {"a": 1})

    def test_fenced_json_block(self):
        self.assertEqual(scoring.parse_output('```json\n{"a": 1}\n```'), {"a": 1})

    def test_json_with_commentary_around_it(self):
        text = 'Here is the extraction:\n{"a": 1}\nLet me know if you need more.'
        self.assertEqual(scoring.parse_output(text), {"a": 1})

    def test_prose_with_no_object_does_not_parse(self):
        self.assertIsNone(scoring.parse_output("I cannot read this document."))

    def test_json_array_is_not_an_object(self):
        self.assertIsNone(scoring.parse_output("[1, 2, 3]"))


class TestScoreCase(unittest.TestCase):
    def test_exact_answer_scores_one(self):
        result = scoring.score_case(GOLDEN, perfect())
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["field_score"], 1.0)
        self.assertEqual(result["hallucinated_fields"], [])

    def test_reformatted_answer_still_scores_one(self):
        restyled = perfect(
            container_id="MRDU 441907-8",
            declared_value_usd="USD 42,300.00",
            gross_weight_kg="18420 kg",
            incoterm="fob",
        )
        result = scoring.score_case(GOLDEN, restyled)
        self.assertTrue(result["exact_match"])

    def test_one_wrong_field_costs_one_ninth(self):
        result = scoring.score_case(GOLDEN, perfect(gross_weight_kg=26455))
        self.assertFalse(result["exact_match"])
        self.assertEqual(result["matched"], 8)
        self.assertAlmostEqual(result["field_score"], 8 / 9)

    def test_filling_an_absent_field_is_counted_as_fabrication(self):
        golden = dict(GOLDEN, incoterm=None)
        result = scoring.score_case(golden, perfect(incoterm="FOB"))
        self.assertEqual(result["hallucinated_fields"], ["incoterm"])
        self.assertFalse(result["exact_match"])

    def test_saying_not_present_for_an_absent_field_is_correct(self):
        golden = dict(GOLDEN, incoterm=None)
        result = scoring.score_case(golden, perfect(incoterm="N/A"))
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["hallucinated_fields"], [])

    def test_omitted_key_is_a_miss_and_is_named(self):
        answer = perfect()
        del answer["incoterm"]
        result = scoring.score_case(GOLDEN, answer)
        self.assertEqual(result["missing_keys"], ["incoterm"])
        self.assertFalse(result["fields"]["incoterm"]["present"])

    def test_omitting_a_field_that_is_absent_is_still_correct(self):
        golden = dict(GOLDEN, incoterm=None)
        answer = perfect()
        del answer["incoterm"]
        result = scoring.score_case(golden, answer)
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["hallucinated_fields"], [])

    def test_unparseable_response_scores_zero_without_counting_fabrication(self):
        result = scoring.score_case(GOLDEN, "I cannot read this document.")
        self.assertTrue(result["parse_error"])
        self.assertEqual(result["field_score"], 0.0)
        self.assertEqual(result["hallucinated_fields"], [])

    def test_two_invalid_values_do_not_match_each_other(self):
        golden = dict(GOLDEN, ship_date="03/04/2026")
        result = scoring.score_case(golden, perfect(ship_date="03/04/2026"))
        self.assertFalse(result["fields"]["ship_date"]["match"])


class TestGoldenValidation(unittest.TestCase):
    def test_clean_golden_case_has_no_problems(self):
        self.assertEqual(scoring.validate_golden(GOLDEN), [])

    def test_unnormalizable_golden_value_is_reported(self):
        problems = scoring.validate_golden(dict(GOLDEN, ship_date={}))
        self.assertEqual([field for field, _ in problems], ["ship_date"])

    def test_field_outside_the_schema_is_reported(self):
        problems = scoring.validate_golden(dict(GOLDEN, freight_charge=100))
        self.assertEqual([field for field, _ in problems], ["freight_charge"])


class TestConsistency(unittest.TestCase):
    def test_identical_answers_agree_completely(self):
        self.assertEqual(scoring.modal_agreement(["a", "a", "a"]), 1.0)

    def test_one_deviation_in_three_runs(self):
        self.assertAlmostEqual(scoring.modal_agreement(["a", "a", "b"]), 2 / 3)

    def test_reformatting_across_runs_is_not_drift(self):
        first = scoring.canonical_answer(GOLDEN, perfect())
        second = scoring.canonical_answer(
            GOLDEN, perfect(declared_value_usd="USD 42,300.00", incoterm="fob")
        )
        self.assertEqual(first, second)
        self.assertEqual(scoring.modal_agreement([first, second]), 1.0)

    def test_a_changed_answer_is_drift(self):
        first = scoring.canonical_answer(GOLDEN, perfect())
        second = scoring.canonical_answer(GOLDEN, perfect(hazmat=True))
        self.assertNotEqual(first, second)


class TestVerdictsAndMovement(unittest.TestCase):
    def scored(self, *matches):
        return [{"exact_match": flag} for flag in matches]

    def test_all_repeats_right_is_a_pass(self):
        self.assertEqual(scoring.case_verdict(self.scored(True, True, True)), "pass")

    def test_no_repeat_right_is_a_fail(self):
        self.assertEqual(scoring.case_verdict(self.scored(False, False)), "fail")

    def test_some_repeats_right_is_unstable(self):
        self.assertEqual(scoring.case_verdict(self.scored(True, False, True)), "unstable")

    def test_pass_to_fail_is_a_regression(self):
        delta = scoring.compare_versions({"A": "pass"}, {"A": "fail"})
        self.assertEqual([item["case_id"] for item in delta["regressions"]], ["A"])
        self.assertEqual(delta["fixes"], [])

    def test_pass_to_unstable_is_also_a_regression(self):
        delta = scoring.compare_versions({"A": "pass"}, {"A": "unstable"})
        self.assertEqual([item["case_id"] for item in delta["regressions"]], ["A"])

    def test_fail_to_pass_is_a_fix(self):
        delta = scoring.compare_versions({"A": "fail"}, {"A": "pass"})
        self.assertEqual([item["case_id"] for item in delta["fixes"]], ["A"])

    def test_still_failing_is_neither(self):
        delta = scoring.compare_versions({"A": "fail"}, {"A": "fail"})
        self.assertEqual(delta["regressions"], [])
        self.assertEqual(delta["fixes"], [])


class TestSummarizeVariant(unittest.TestCase):
    def test_metrics_roll_up_across_cases_and_repeats(self):
        golden_null = dict(GOLDEN, incoterm=None)
        rows = {
            "CASE-1": [scoring.score_case(GOLDEN, perfect()) for _ in range(3)],
            "CASE-2": [
                scoring.score_case(golden_null, perfect(incoterm="FOB")),
                scoring.score_case(golden_null, perfect(incoterm=None)),
                scoring.score_case(golden_null, perfect(incoterm=None)),
            ],
        }
        summary = scoring.summarize_variant(rows)
        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["rows"], 6)
        self.assertEqual(summary["fields_total"], 54)
        self.assertEqual(summary["fields_matched"], 53)
        self.assertEqual(summary["cases_exact"], 5)
        self.assertEqual(summary["fabricated_fields"], 1)
        self.assertEqual(summary["null_fields"], 3)
        self.assertAlmostEqual(summary["hallucination_rate"], 1 / 3)
        self.assertEqual(summary["unstable_cases"], ["CASE-2"])
        self.assertEqual(summary["verdicts"], {"CASE-1": "pass", "CASE-2": "unstable"})


class TestVersionKey(unittest.TestCase):
    def test_short_label_passes_through(self):
        self.assertEqual(scoring.version_key("v2"), "v2")

    def test_composite_promptfoo_label_reduces_to_the_version(self):
        label = "v2: prompts\\extract-v2.txt: You extract structured data"
        self.assertEqual(scoring.version_key(label), "v2")

    def test_missing_label_is_named_rather_than_crashing(self):
        self.assertEqual(scoring.version_key(None), "unknown")


class TestDescribeMisses(unittest.TestCase):
    def test_names_the_wrong_field_and_both_values(self):
        result = scoring.score_case(GOLDEN, perfect(gross_weight_kg=26455))
        text = scoring.describe_misses(result)
        self.assertIn("8/9 fields", text)
        self.assertIn("gross_weight_kg", text)

    def test_calls_out_fabrication(self):
        golden = dict(GOLDEN, incoterm=None)
        text = scoring.describe_misses(scoring.score_case(golden, perfect(incoterm="FOB")))
        self.assertIn("fabricated", text)

    def test_parse_failure_says_so(self):
        text = scoring.describe_misses(scoring.score_case(GOLDEN, "nope"))
        self.assertIn("did not parse", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
