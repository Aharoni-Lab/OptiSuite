from __future__ import annotations

from abc import ABC, abstractmethod

from core.results import AnalyzerConfig, AnalyzerResult, ChartType, ImageContext


class ResolutionAnalyzer(ABC):
    chart_type: ChartType
    display_name: str

    def __init__(self, config: AnalyzerConfig | None = None):
        self.config = config or AnalyzerConfig(chart_type=self.chart_type)

    @abstractmethod
    def probe(self, context: ImageContext) -> float:
        raise NotImplementedError

    @abstractmethod
    def analyze(self, context: ImageContext) -> AnalyzerResult:
        raise NotImplementedError

