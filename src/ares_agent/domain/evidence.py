"""Evidence models."""

from pydantic import BaseModel, Field


class EvidencePackage(BaseModel):
    """Evidence package returned by the refined path."""

    event_id: str
    source_image_uri: str | None = None
    crop_image_uris: list[str] = Field(default_factory=list)
    overlay_image_uris: list[str] = Field(default_factory=list)
    mask_uri: str | None = None
    evidence_basis_summary: str | None = None
    archive_readiness: bool = False
    rejection_reason: str | None = None
