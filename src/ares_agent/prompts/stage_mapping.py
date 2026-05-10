"""Mapping between data_engine Step1/Step2 outputs and Ares Agent domain models."""

from __future__ import annotations

import json

from ares_agent.domain.stage1_output import Stage1Output
from ares_agent.domain.stage2_output import Stage2Candidate, Stage2Output
from ares_agent.workflows.inspection_event_workflow import (
    EvidenceJudgeResult,
    PreliminaryCandidate,
    PreliminaryResult,
)


def map_stage1_to_preliminary(stage1: Stage1Output) -> PreliminaryResult:
    """Map data_engine Stage1Output to Ares Agent PreliminaryResult.

    Step1 only produces structured facts (no violation judgment),
    so we produce a single preliminary result with the scene analysis.
    The actual violation candidates come from Step2.
    """
    return PreliminaryResult(
        environment_analysis=stage1.environment_analysis,
        scene_elements=stage1.scene_elements,
        candidates=[
            PreliminaryCandidate(
                violation_category="none",
                open_risk_type="",
                confidence=0.0,
                evidence_reasoning="step1 scene parsing complete, awaiting step2 judgment",
                segmentation_targets=[],
                relation_hint="",
            )
        ],
    )


def map_stage2_to_preliminary(
    stage2: Stage2Output,
    stage1: Stage1Output,
) -> PreliminaryResult:
    """Map data_engine Stage2Output to Ares Agent PreliminaryResult.

    Each Stage2Candidate with a real violation becomes a PreliminaryCandidate.
    """
    candidates: list[PreliminaryCandidate] = []
    for sc in stage2.candidates:
        if "no_violation" in sc.violation_category:
            continue
        for cat in sc.violation_category:
            if cat == "no_violation":
                continue
            candidates.append(
                PreliminaryCandidate(
                    violation_category=cat,
                    open_risk_type="",
                    confidence=sc.confidence,
                    evidence_reasoning=sc.evidence_reasoning,
                    segmentation_targets=list(sc.segmentation_targets),
                    relation_hint=sc.relation_hint,
                )
            )
    if not candidates:
        candidates = [
            PreliminaryCandidate(
                violation_category="none",
                open_risk_type="",
                confidence=0.0,
                evidence_reasoning="no violation detected",
                segmentation_targets=[],
                relation_hint="",
            )
        ]
    return PreliminaryResult(
        environment_analysis=stage1.environment_analysis,
        scene_elements=stage1.scene_elements,
        candidates=candidates,
    )


def map_stage2_to_evidence_judge(stage2: Stage2Output) -> EvidenceJudgeResult:
    """Map data_engine Stage2Output to Ares Agent EvidenceJudgeResult.

    Uses the first non-no_violation candidate and its supporting fact verifications.
    """
    violation_candidates = [
        c for c in stage2.candidates
        if "no_violation" not in c.violation_category
    ]
    if not violation_candidates:
        return EvidenceJudgeResult(
            final_category="none",
            final_confidence=0.0,
            evidence_basis_match=False,
            violation_relation_confirmed=False,
            exception_excluded=True,
            archive_readiness=False,
            review_required=False,
            rejection_reason="no violation found",
        )

    candidate = violation_candidates[0]
    supported_facts = [
        f for f in stage2.fact_verifications
        if f.relation_index in candidate.evidence_relation_indices
        and f.verification_result in ("supported", "weakly_supported")
    ]
    has_strong_support = any(
        f.verification_result == "supported" for f in supported_facts
    )

    return EvidenceJudgeResult(
        final_category=candidate.violation_category[0],
        final_confidence=candidate.confidence,
        evidence_basis_match=len(supported_facts) > 0,
        violation_relation_confirmed=has_strong_support,
        exception_excluded=False,
        archive_readiness=has_strong_support and candidate.confidence >= 0.7,
        review_required=not has_strong_support or candidate.confidence < 0.5,
        rejection_reason=None if has_strong_support else "evidence insufficient",
        violation_relation_summary=candidate.evidence_reasoning,
    )


def reconstruct_stage1_json(preliminary: PreliminaryResult) -> str:
    """Reconstruct a minimal Stage1Output JSON from PreliminaryResult.

    Used when Step2 needs a Stage1Output JSON but we only have the
    PreliminaryResult (e.g., in the EvidenceJudgeClient.judge() interface).
    """
    stage1 = Stage1Output(
        environment_analysis=preliminary.environment_analysis,
        scene_elements=list(preliminary.scene_elements),
        key_anchors=[],
        key_relations=[],
    )
    return stage1.model_dump_json(ensure_ascii=False)


def stage2_candidates_to_filtered_list(
    stage2: Stage2Output,
) -> list[Stage2Candidate]:
    """Extract non-no_violation candidates from Stage2Output."""
    return [
        c for c in stage2.candidates
        if "no_violation" not in c.violation_category
    ]
