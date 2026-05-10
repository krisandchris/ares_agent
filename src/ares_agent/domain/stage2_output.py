"""data_engine Step2 output models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ares_agent.domain.stage1_output import BBox

VerificationResult = Literal[
    "supported",
    "weakly_supported",
    "unsupported",
    "unclear",
]

SampleCategory = Literal[
    "positive samples",
    "negative samples",
    "hard boundary samples",
]

VisibilityLevel = Literal[
    "clear",
    "partial",
    "tiny",
    "blurry",
    "occluded",
]

InformationLossType = Literal[
    "none",
    "occlusion",
    "boundary_truncation",
]


class FactVerification(BaseModel):
    relation_index: int
    subject: str
    relation: str
    object: str
    bbox: BBox = Field(min_length=4, max_length=4)
    visibility_level: VisibilityLevel
    information_loss_type: InformationLossType
    key_attributes_visible: list[str]
    subject_visible: bool
    subject_match: bool
    bbox_observation: str = Field(min_length=1)
    global_context_observation: str = Field(min_length=1)
    verification_result: VerificationResult
    verification_confidence: float = Field(ge=0.0, le=1.0)


class Stage2Candidate(BaseModel):
    violation_category: list[str]
    evidence_relation_indices: list[int]
    evidence_reasoning: str = Field(min_length=1)
    relation_hint: str = ""
    segmentation_targets: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    sample_category: SampleCategory


class Stage2Output(BaseModel):
    sample_id: str = Field(min_length=1)
    fact_verifications: list[FactVerification]
    candidates: list[Stage2Candidate]
