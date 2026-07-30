"""Tests for the report layer, run against the committed offline baseline.

These assertions pin the numbers quoted in README.md to the run recorded in
runs/offline-baseline.json. Change the golden set, a prompt, or a fixture profile and
this file fails until the documented figures are brought back in line.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))

import report  # noqa: E402

BASELINE = os.path.join(ROOT, "runs", "offline-baseline.json")

# model, prompt version, fields matched, fields total, exact rows, rows, fabricated,
# null fields, consistency
EXPECTED_VARIANTS = [
    ("gpt-oss-120b", "v1", 393, 405, 33, 45, 0, 9, 1.0),
    ("gpt-oss-120b", "v2", 399, 405, 39, 45, 6, 9, 1.0),
    ("llama-3.1-8b", "v1", 384, 405, 24, 45, 3, 9, 43.0 / 45),
    ("llama-3.1-8b", "v2", 391, 405, 31, 45, 9, 9, 43.0 / 45),
    ("llama-3.3-70b", "v1", 390, 405, 30, 45, 3, 9, 1.0),
    ("llama-3.3-70b", "v2", 396, 405, 36, 45, 9, 9, 1.0),
]


def run_main(*args):
    """Call the report CLI, swallow its output, and return the exit code."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = report.main([BASELINE] + list(args))
    return code, buffer.getvalue()


class TestBaselineLoads(unittest.TestCase):
    def setUp(self):
        self.payload, self.rows = report.load_rows(BASELINE)

    def test_every_response_is_present(self):
        self.assertEqual(len(self.rows), 270)

    def test_the_run_recorded_three_repeats(self):
        self.assertEqual(self.payload["runtimeOptions"]["repeat"], 3)

    def test_every_row_carries_its_golden_answer(self):
        for row in self.rows:
            self.assertEqual(len(row["expected"]), 9, row["case_id"])

    def test_versions_and_models_are_labelled_cleanly(self):
        self.assertEqual(sorted({row["version"] for row in self.rows}), ["v1", "v2"])
        self.assertEqual(
            sorted({row["model"] for row in self.rows}),
            ["gpt-oss-120b", "llama-3.1-8b", "llama-3.3-70b"],
        )

    def test_the_golden_set_has_no_defects(self):
        self.assertEqual(report.golden_problems(self.rows), [])

    def test_no_provider_errors_in_the_baseline(self):
        _, _, errors = report.score_rows(self.rows)
        self.assertEqual(errors, [])


class TestBaselineMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, rows = report.load_rows(BASELINE)
        cls.grouped, cls.integrity, cls.errors = report.score_rows(rows)
        cls.summaries = report.build_summaries(cls.grouped)

    def test_every_recomputed_score_matches_promptfoo(self):
        self.assertEqual(self.integrity["checked"], 270)
        self.assertEqual(self.integrity["agreed"], 270)
        self.assertEqual(self.integrity["disagreements"], [])

    def test_each_variant_matches_the_documented_figures(self):
        for row in EXPECTED_VARIANTS:
            model, version, matched, total, exact, rows, fab, nulls, consistency = row
            summary = self.summaries[(model, version)]
            label = "%s %s" % (model, version)
            self.assertEqual(summary["fields_matched"], matched, label)
            self.assertEqual(summary["fields_total"], total, label)
            self.assertEqual(summary["cases_exact"], exact, label)
            self.assertEqual(summary["rows"], rows, label)
            self.assertEqual(summary["fabricated_fields"], fab, label)
            self.assertEqual(summary["null_fields"], nulls, label)
            self.assertAlmostEqual(summary["consistency"], consistency, places=6, msg=label)

    def test_no_response_failed_to_parse(self):
        for summary in self.summaries.values():
            self.assertEqual(summary["parse_errors"], 0)

    def test_v2_raises_field_accuracy_for_every_model(self):
        for model in ("gpt-oss-120b", "llama-3.1-8b", "llama-3.3-70b"):
            self.assertGreater(
                self.summaries[(model, "v2")]["field_accuracy"],
                self.summaries[(model, "v1")]["field_accuracy"],
                model,
            )

    def test_v2_also_raises_fabrication_for_every_model(self):
        for model in ("gpt-oss-120b", "llama-3.1-8b", "llama-3.3-70b"):
            self.assertGreater(
                self.summaries[(model, "v2")]["hallucination_rate"],
                self.summaries[(model, "v1")]["hallucination_rate"],
                model,
            )

    def test_only_the_small_model_drifts_between_runs(self):
        self.assertEqual(self.summaries[("llama-3.1-8b", "v1")]["unstable_cases"], ["BOL-006", "INV-005"])
        self.assertEqual(self.summaries[("llama-3.3-70b", "v1")]["unstable_cases"], [])
        self.assertEqual(self.summaries[("gpt-oss-120b", "v1")]["unstable_cases"], [])

    def test_the_same_two_cases_regress_on_all_three_models(self):
        for model in ("gpt-oss-120b", "llama-3.1-8b", "llama-3.3-70b"):
            delta = report.scoring.compare_versions(
                self.summaries[(model, "v1")]["verdicts"],
                self.summaries[(model, "v2")]["verdicts"],
            )
            self.assertEqual(
                [item["case_id"] for item in delta["regressions"]],
                ["BOL-007", "BOL-009"],
                model,
            )
            self.assertEqual(len(delta["fixes"]), 4, model)


class TestProviderErrorsAreExcluded(unittest.TestCase):
    def payload_with_one_failed_call(self):
        golden = {"shipment_id": "SHP-1", "hazmat": False}
        good = {
            "provider": {"label": "m1"},
            "prompt": {"label": "v1: prompts/extract-v1.txt: text"},
            "testCase": {"vars": {"case_id": "C1", "branch": "b", "expected": golden}},
            "response": {"output": json.dumps(golden)},
            "score": 1.0,
            "success": True,
            "failureReason": 0,
        }
        errored = {
            "provider": {"label": "m1"},
            "prompt": {"label": "v1: prompts/extract-v1.txt: text"},
            "testCase": {"vars": {"case_id": "C2", "branch": "b", "expected": golden}},
            "response": {"error": "429 rate limited"},
            "error": "429 rate limited",
            "score": 0,
            "success": False,
            "failureReason": 2,
        }
        return {"evalId": "test", "results": {"results": [good, errored]}}

    def test_a_failed_call_is_counted_but_not_scored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "run.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(self.payload_with_one_failed_call(), handle)
            _, rows = report.load_rows(path)
            grouped, integrity, errors = report.score_rows(rows)

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["case_id"], "C2")
        summary = report.build_summaries(grouped)[("m1", "v1")]
        self.assertEqual(summary["cases"], 1)
        self.assertEqual(summary["field_accuracy"], 1.0)

    def test_an_assertion_failure_is_not_read_as_a_failed_call(self):
        payload = self.payload_with_one_failed_call()
        assert_failure = dict(payload["results"]["results"][1])
        assert_failure["response"] = {"output": '{"shipment_id": "WRONG"}'}
        assert_failure["error"] = "1/2 fields; shipment_id (got 'WRONG')"
        assert_failure["failureReason"] = 1
        payload["results"]["results"][1] = assert_failure

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "run.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            _, rows = report.load_rows(path)
            _, _, errors = report.score_rows(rows)

        self.assertEqual(errors, [])


class TestCommandLine(unittest.TestCase):
    def test_a_clean_run_passes(self):
        code, output = run_main()
        self.assertEqual(code, 0)
        self.assertIn("PASS", output)
        self.assertIn("270 of 270", output)

    def test_the_regression_gate_fails_the_run(self):
        code, output = run_main("--fail-on-regression")
        self.assertEqual(code, 1)
        self.assertIn("6 case regression(s)", output)

    def test_an_accuracy_gate_below_every_variant_passes(self):
        code, _ = run_main("--fail-under", "0.90")
        self.assertEqual(code, 0)

    def test_an_accuracy_gate_above_some_variants_fails(self):
        code, output = run_main("--fail-under", "0.97")
        self.assertEqual(code, 1)
        self.assertIn("llama-3.1-8b v1", output)

    def test_the_report_names_both_regressed_cases(self):
        _, output = run_main()
        self.assertIn("BOL-007", output)
        self.assertIn("BOL-009", output)
        self.assertIn("carrier-name-without-scac", output)

    def test_metrics_can_be_written_as_json(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "metrics.json")
            code, _ = run_main("--json", path)
            with open(path, encoding="utf-8") as handle:
                export = json.load(handle)
        self.assertEqual(code, 0)
        self.assertEqual(len(export["variants"]), 6)
        self.assertEqual(
            sorted({item["case_id"] for items in export["regressions"].values() for item in items}),
            ["BOL-007", "BOL-009"],
        )

    def test_a_missing_file_exits_two(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = report.main(["no-such-file.json"])
        self.assertEqual(code, 2)

    def test_a_file_without_results_exits_two(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "empty.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"evalId": "x"}, handle)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = report.main([path])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
