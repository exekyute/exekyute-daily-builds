"""Tests for the offline replay provider that stands in for a hosted model."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))

import replay_provider  # noqa: E402
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


def context_for(case_id="BOL-001", expected=None, version="v1", repeat=0):
    return {
        "vars": {"case_id": case_id, "expected": expected or dict(GOLDEN)},
        "prompt": {"label": "%s: prompts/extract-%s.txt: You extract" % (version, version)},
        "repeatIndex": repeat,
    }


class TestBuildAnswer(unittest.TestCase):
    def test_no_deviations_returns_the_golden_answer(self):
        answer = replay_provider.build_answer(GOLDEN, {}, "BOL-001", 0)
        self.assertEqual(answer, GOLDEN)

    def test_errors_are_applied_on_every_repeat(self):
        profile = {"errors": {"BOL-002": {"gross_weight_kg": 26455}}}
        for repeat in range(3):
            answer = replay_provider.build_answer(GOLDEN, profile, "BOL-002", repeat)
            self.assertEqual(answer["gross_weight_kg"], 26455)

    def test_errors_on_another_case_are_left_alone(self):
        profile = {"errors": {"BOL-002": {"gross_weight_kg": 26455}}}
        answer = replay_provider.build_answer(GOLDEN, profile, "BOL-001", 0)
        self.assertEqual(answer["gross_weight_kg"], 18420.0)

    def test_unstable_variants_cycle_by_repeat_index(self):
        profile = {"unstable": {"BOL-006": [{}, {"hazmat": True}, {}]}}
        first = replay_provider.build_answer(GOLDEN, profile, "BOL-006", 0)
        second = replay_provider.build_answer(GOLDEN, profile, "BOL-006", 1)
        third = replay_provider.build_answer(GOLDEN, profile, "BOL-006", 2)
        self.assertFalse(first["hazmat"])
        self.assertTrue(second["hazmat"])
        self.assertFalse(third["hazmat"])

    def test_repeat_index_wraps_past_the_variant_count(self):
        profile = {"unstable": {"BOL-006": [{}, {"hazmat": True}]}}
        fourth = replay_provider.build_answer(GOLDEN, profile, "BOL-006", 3)
        self.assertTrue(fourth["hazmat"])

    def test_omitted_fields_are_dropped_from_the_answer(self):
        profile = {"omits": {"INV-006": ["incoterm"]}}
        answer = replay_provider.build_answer(GOLDEN, profile, "INV-006", 0)
        self.assertNotIn("incoterm", answer)

    def test_the_golden_answer_is_not_mutated(self):
        profile = {"errors": {"BOL-001": {"hazmat": True}}}
        replay_provider.build_answer(GOLDEN, profile, "BOL-001", 0)
        self.assertFalse(GOLDEN["hazmat"])


class TestRenderStyles(unittest.TestCase):
    def test_container_is_written_the_way_it_is_stamped(self):
        self.assertEqual(replay_provider.spaced_container("MRDU4419078"), "MRDU 441907-8")

    def test_short_container_is_left_as_is(self):
        self.assertEqual(replay_provider.spaced_container("MRDU441"), "MRDU441")

    def test_fenced_style_wraps_the_object(self):
        text = replay_provider.render_answer(dict(GOLDEN), {"fenced": True})
        self.assertTrue(text.startswith("```json"))
        self.assertIsNotNone(scoring.parse_output(text))

    def test_na_style_writes_text_instead_of_null(self):
        answer = dict(GOLDEN, incoterm=None)
        text = replay_provider.render_answer(answer, {"nulls": "na_text"})
        self.assertIn('"N/A"', text)

    def test_every_style_scores_the_same_after_normalization(self):
        styles = [
            {},
            {"fenced": True},
            {"nulls": "na_text"},
            {"money": "usd_commas", "container": "spaced"},
        ]
        for style in styles:
            text = replay_provider.render_answer(dict(GOLDEN), style)
            result = scoring.score_case(GOLDEN, text)
            self.assertTrue(result["exact_match"], style)


class TestShippedProfiles(unittest.TestCase):
    def test_the_fixture_file_holds_three_models_with_both_versions(self):
        profiles = replay_provider.load_profiles()
        self.assertEqual(
            sorted(profiles), ["gpt-oss-120b", "llama-3.1-8b", "llama-3.3-70b"]
        )
        for name, profile in profiles.items():
            self.assertEqual(sorted(profile["versions"]), ["v1", "v2"], name)


class TestCallApi(unittest.TestCase):
    def test_a_known_model_answers_a_clean_case_correctly(self):
        response = replay_provider.call_api(
            "prompt text", {"config": {"model": "llama-3.3-70b"}}, context_for()
        )
        self.assertNotIn("error", response)
        self.assertTrue(scoring.score_case(GOLDEN, response["output"])["exact_match"])

    def test_a_written_error_shows_up_in_the_answer(self):
        golden = dict(GOLDEN, gross_weight_kg=11999.8)
        response = replay_provider.call_api(
            "prompt text",
            {"config": {"model": "llama-3.3-70b"}},
            context_for(case_id="BOL-002", expected=golden, version="v1"),
        )
        parsed = scoring.parse_output(response["output"])
        self.assertEqual(parsed["gross_weight_kg"], 26455)

    def test_the_same_case_is_fixed_under_v2(self):
        golden = dict(GOLDEN, gross_weight_kg=11999.8)
        response = replay_provider.call_api(
            "prompt text",
            {"config": {"model": "llama-3.3-70b"}},
            context_for(case_id="BOL-002", expected=golden, version="v2"),
        )
        self.assertTrue(scoring.score_case(golden, response["output"])["exact_match"])

    def test_unknown_model_returns_an_error(self):
        response = replay_provider.call_api(
            "prompt text", {"config": {"model": "no-such-model"}}, context_for()
        )
        self.assertIn("error", response)

    def test_unknown_prompt_version_returns_an_error(self):
        response = replay_provider.call_api(
            "prompt text",
            {"config": {"model": "llama-3.3-70b"}},
            context_for(version="v9"),
        )
        self.assertIn("error", response)

    def test_a_case_without_expected_values_returns_an_error(self):
        context = context_for()
        context["vars"]["expected"] = {}
        response = replay_provider.call_api(
            "prompt text", {"config": {"model": "llama-3.3-70b"}}, context
        )
        self.assertIn("error", response)

    def test_repeat_index_falls_back_to_the_injected_var(self):
        golden = dict(GOLDEN, hazmat=True)
        context = context_for(case_id="BOL-006", expected=golden, version="v1")
        del context["repeatIndex"]
        context["vars"]["__repeatIndex"] = 1
        response = replay_provider.call_api(
            "prompt text", {"config": {"model": "llama-3.1-8b"}}, context
        )
        parsed = scoring.parse_output(response["output"])
        self.assertFalse(parsed["hazmat"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
