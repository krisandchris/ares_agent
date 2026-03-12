"""JSON-backed mock model clients for local development."""

from __future__ import annotations

import json
from pathlib import Path

from ares_agent.domain.json_types import JsonObject

from ares_agent.domain.events import EventSeed
from ares_agent.workflows.inspection_event_workflow import (
    EvidenceJudgeResult,
    PreliminaryResult,
    SegmentationResult,
)

def _load_json(path: Path) -> JsonObject:
    fixture_path = path if path.is_absolute() else Path.cwd() / path
    return json.loads(fixture_path.read_text(encoding="utf-8"))


class MockPreliminaryClient:
    """Mock VLM-1 client backed by a static fixture."""

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def analyze_from_fixture(self) -> PreliminaryResult:
        return PreliminaryResult.model_validate(_load_json(self.fixture_path))

    def analyze(self, seed: EventSeed) -> PreliminaryResult:
        del seed
        return self.analyze_from_fixture()


class MockSegmentationClient:
    """Mock SAM3 client backed by a static fixture."""

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def segment_from_fixture(self) -> SegmentationResult:
        return SegmentationResult.model_validate(_load_json(self.fixture_path))

    def segment(self, image_uri: str, targets: list[str]) -> SegmentationResult:
        del image_uri, targets
        return self.segment_from_fixture()


class MockEvidenceJudgeClient:
    """Mock VLM-2 client backed by a static fixture."""

    def __init__(self, fixture_path: Path) -> None:
        self.fixture_path = fixture_path

    def judge_from_fixture(self) -> EvidenceJudgeResult:
        return EvidenceJudgeResult.model_validate(_load_json(self.fixture_path))

    def judge(
        self,
        *,
        event_id: str,
        category_code: str,
        overlay_image: str | None = None,
        mask_labels: list[str] | None = None,
        relation_hint: str = "",
        segmentation_status: str = "ok",
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
    ) -> EvidenceJudgeResult:
        del (
            event_id,
            overlay_image,
            mask_labels,
            relation_hint,
            segmentation_status,
            category_code,
            evidence_basis_summary,
            preliminary,
        )
        return self.judge_from_fixture()
