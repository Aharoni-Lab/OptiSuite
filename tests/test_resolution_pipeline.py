from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import cv2

from analyzers.usaf import USAFAnalyzer, USAFAnalyzerConfig, USAF_SCORE_TABLE
from core.registration import load_image_context
from core.results import AnalyzerConfig
from core.router import TargetRouter


class ResolutionPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest_path = Path("benchmarks/manifest.json")
        cls.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        cls.router = TargetRouter(
            AnalyzerConfig(
                contrast_threshold=0.2,
                show_preview=False,
                debug_mode=False,
                use_detection_fallback=False,
                allow_model_assist=False,
            )
        )

    def test_router_matches_expected_chart_type_for_supported_benchmarks(self) -> None:
        for entry in self.manifest:
            if not entry["expected_success"]:
                continue
            with self.subTest(entry=entry["name"]):
                decision, _analyzer = self.router.route(entry["path"])
                self.assertEqual(decision.chart_type, entry["expected_chart_type"])
                self.assertGreaterEqual(decision.confidence, 0.3)

    def test_analyzers_succeed_on_their_benchmarks(self) -> None:
        for entry in self.manifest:
            if not entry["expected_success"]:
                continue
            with self.subTest(entry=entry["name"]):
                _decision, result = self.router.analyze_image(
                    entry["path"],
                    override_chart_type=entry["expected_chart_type"],
                )
                self.assertTrue(result.success)
                self.assertNotEqual(result.reading.value, "unresolved")
                self.assertGreater(len(result.contrast_curve), 0)

    def test_failure_case_reports_unsuccessful_result(self) -> None:
        blank_entry = next(entry for entry in self.manifest if entry["name"] == "blank_failure")
        _decision, result = self.router.analyze_image(blank_entry["path"], override_chart_type="contrast")
        self.assertFalse(result.success)
        self.assertEqual(result.reading.value, "unresolved")
        self.assertIsNotNone(result.error)

    def test_usaf_auto_flip_detects_mirrored_target(self) -> None:
        source_path = Path("test_image_g6e6_copy.png")
        image = cv2.imread(str(source_path))
        self.assertIsNotNone(image)

        with tempfile.TemporaryDirectory() as temp_dir:
            flipped_path = Path(temp_dir) / "mirrored_usaf.png"
            cv2.imwrite(str(flipped_path), cv2.flip(image, 1))

            normal_result = USAFAnalyzer(
                USAFAnalyzerConfig(allow_model_assist=True, flip_mode="auto")
            ).analyze(load_image_context(str(source_path)))
            flipped_result = USAFAnalyzer(
                USAFAnalyzerConfig(allow_model_assist=True, flip_mode="auto")
            ).analyze(load_image_context(str(flipped_path)))

        self.assertFalse(normal_result.reading.details["flipped_target"])
        self.assertTrue(flipped_result.reading.details["flipped_target"])
        self.assertEqual(normal_result.reading.details["group"], flipped_result.reading.details["group"])
        self.assertEqual(normal_result.reading.details["element"], flipped_result.reading.details["element"])

    def test_usaf_threshold_changes_resolvable_result(self) -> None:
        source_path = Path("test_image_g6e6_copy.png")
        context = load_image_context(str(source_path))

        relaxed_result = USAFAnalyzer(
            USAFAnalyzerConfig(allow_model_assist=True, flip_mode="auto", contrast_threshold=0.2)
        ).analyze(context)
        strict_result = USAFAnalyzer(
            USAFAnalyzerConfig(allow_model_assist=True, flip_mode="auto", contrast_threshold=0.99)
        ).analyze(context)

        self.assertTrue(relaxed_result.success)
        self.assertEqual(relaxed_result.reading.details["group"], 6)
        self.assertEqual(relaxed_result.reading.details["element"], 6)
        self.assertFalse(strict_result.success)
        self.assertEqual(strict_result.reading.value, "unresolved")

    def test_usaf_score_table_extends_through_group_7(self) -> None:
        self.assertIn((7, 1), USAF_SCORE_TABLE)
        self.assertIn((7, 6), USAF_SCORE_TABLE)
        self.assertEqual(len(USAF_SCORE_TABLE), 27)


if __name__ == "__main__":
    unittest.main()

