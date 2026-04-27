from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yolo_model
from analyzers.contrast_chart import ContrastChartAnalyzer, ContrastChartAnalyzerConfig
from analyzers.grid import GridAnalyzer, GridAnalyzerConfig
from analyzers.siemens import SiemensAnalyzer, SiemensAnalyzerConfig
from analyzers.slanted_edge import SlantedEdgeAnalyzer, SlantedEdgeAnalyzerConfig
from analyzers.usaf import USAFAnalyzer, USAFAnalyzerConfig
from core.registration import load_image_context
from core.results import AnalyzerConfig, AnalyzerResult, ChartType, RouterDecision


SUPPORTED_CHART_TYPES: list[ChartType] = ["auto", "usaf", "siemens", "grid", "slanted_edge", "contrast"]


class TargetRouter:
    def __init__(self, config: AnalyzerConfig | None = None):
        self.config = config or AnalyzerConfig()

    def _build_analyzers(self) -> dict[str, object]:
        return {
            "usaf": USAFAnalyzer(
                USAFAnalyzerConfig(
                    contrast_threshold=self.config.contrast_threshold,
                    show_preview=self.config.show_preview,
                    debug_mode=self.config.debug_mode,
                    use_detection_fallback=self.config.use_detection_fallback,
                    allow_model_assist=self.config.allow_model_assist,
                    flip_mode=self.config.flip_mode,
                )
            ),
            "siemens": SiemensAnalyzer(
                SiemensAnalyzerConfig(
                    contrast_threshold=self.config.contrast_threshold,
                    show_preview=self.config.show_preview,
                    debug_mode=self.config.debug_mode,
                )
            ),
            "grid": GridAnalyzer(
                GridAnalyzerConfig(
                    contrast_threshold=self.config.contrast_threshold,
                    show_preview=self.config.show_preview,
                    debug_mode=self.config.debug_mode,
                )
            ),
            "slanted_edge": SlantedEdgeAnalyzer(
                SlantedEdgeAnalyzerConfig(
                    contrast_threshold=self.config.contrast_threshold,
                    show_preview=self.config.show_preview,
                    debug_mode=self.config.debug_mode,
                )
            ),
            "contrast": ContrastChartAnalyzer(
                ContrastChartAnalyzerConfig(
                    contrast_threshold=self.config.contrast_threshold,
                    show_preview=self.config.show_preview,
                    debug_mode=self.config.debug_mode,
                )
            ),
        }

    def route(self, image_path: str, override_chart_type: ChartType = "auto") -> tuple[RouterDecision, object]:
        analyzers = self._build_analyzers()
        context = load_image_context(image_path)

        if override_chart_type != "auto":
            return (
                RouterDecision(
                    chart_type=override_chart_type,
                    confidence=1.0,
                    reason="User override",
                    candidates={override_chart_type: 1.0},
                ),
                analyzers[override_chart_type],
            )

        scores = {chart_type: float(analyzer.probe(context)) for chart_type, analyzer in analyzers.items()}
        best_chart_type = max(scores, key=scores.get)
        best_score = scores[best_chart_type]
        used_model_fallback = False
        reason = "Heuristic target classification"

        if scores.get("siemens", 0.0) >= 0.85 and scores["siemens"] >= best_score - 0.08:
            best_chart_type = "siemens"
            best_score = scores["siemens"]
            reason = "Heuristic target classification with circular-pattern preference"
        elif scores.get("contrast", 0.0) >= 0.85 and scores["contrast"] >= best_score - 0.05:
            best_chart_type = "contrast"
            best_score = scores["contrast"]
            reason = "Heuristic target classification with patch-pattern preference"

        if self.config.use_detection_fallback and best_score < 0.55:
            try:
                detections, _result, _image = yolo_model.extract_yolo_detections(image_path)
                if len(detections) >= 10:
                    best_chart_type = "usaf"
                    best_score = max(best_score, 0.8)
                    used_model_fallback = True
                    reason = "YOLO fallback detected dense USAF-like elements"
            except Exception:
                pass

        decision = RouterDecision(
            chart_type=best_chart_type,
            confidence=best_score,
            reason=reason,
            candidates=scores,
            used_model_fallback=used_model_fallback,
        )
        return decision, analyzers[best_chart_type]

    def analyze_image(self, image_path: str, override_chart_type: ChartType = "auto") -> tuple[RouterDecision, AnalyzerResult]:
        decision, analyzer = self.route(image_path, override_chart_type=override_chart_type)
        context = load_image_context(image_path)
        result = analyzer.analyze(context)
        result.confidence = max(result.confidence, decision.confidence)
        result.metadata["router"] = {
            "reason": decision.reason,
            "candidates": decision.candidates,
            "used_model_fallback": decision.used_model_fallback,
        }
        return decision, result

