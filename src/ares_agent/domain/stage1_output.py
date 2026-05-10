"""data_engine Step1 output models."""

from __future__ import annotations

from pydantic import BaseModel, Field

BBox = list[int]


class RelationItem(BaseModel):
    subject: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    object: str = Field(min_length=1)
    description: str = Field(min_length=1)
    bbox: BBox = Field(min_length=4, max_length=4)


class Stage1Output(BaseModel):
    environment_analysis: str = Field(min_length=1)
    scene_elements: list[str]
    key_anchors: list[str]
    key_relations: list[RelationItem]
