"""Domain schemas for commerce and steel RFQ extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CommerceLineItem(BaseModel):
    product: str
    color: str | None = None
    quantity: int = Field(gt=0)
    delivery_city: str | None = None
    delivery_deadline: str | None = None
    wants_payment_options: bool = False
    wants_total: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


class CommerceExtraction(BaseModel):
    use_case: Literal["commerce"] = "commerce"
    tenant_id: str
    line_items: list[CommerceLineItem]
    notes: str | None = None


class SteelLineItem(BaseModel):
    grade: str
    norm: str | None = None
    thickness_mm: float
    width_mm: float
    length_mm: float
    quantity_tons: float = Field(gt=0)
    coating: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class SteelExtraction(BaseModel):
    use_case: Literal["steel"] = "steel"
    tenant_id: str
    line_items: list[SteelLineItem]
    notes: str | None = None


ExtractionResult = CommerceExtraction | SteelExtraction
