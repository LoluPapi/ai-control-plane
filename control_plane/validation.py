"""Deterministic domain validation after structured extraction."""

from __future__ import annotations

import json

from control_plane.paths import data_root
from control_plane.schemas import CommerceExtraction, SteelExtraction

DATA_ROOT = data_root()


def _load_steel_grades() -> set[str]:
    payload = json.loads((DATA_ROOT / "knowledge" / "steel_grades.json").read_text())
    return {g.upper() for g in payload["grades"]}


STEEL_GRADES = _load_steel_grades()


def validate_steel_item(item, *, min_confidence: float) -> list[str]:
    errors: list[str] = []
    if item.grade.upper() not in STEEL_GRADES:
        errors.append("Unknown steel grade")
    if item.confidence < min_confidence:
        errors.append("Low-confidence extraction")
    if item.thickness_mm <= 0:
        errors.append("Invalid thickness")
    if item.width_mm <= 0 or item.length_mm <= 0:
        errors.append("Invalid dimensions")
    if item.quantity_tons <= 0:
        errors.append("Invalid quantity")
    return errors


def validate_commerce_item(item, *, catalog_products: set[str], min_confidence: float) -> list[str]:
    errors: list[str] = []
    product_key = item.product.lower()
    if not any(product_key in p for p in catalog_products):
        errors.append("Unknown product for tenant catalogue")
    if item.confidence < min_confidence:
        errors.append("Low-confidence extraction")
    if item.quantity <= 0:
        errors.append("Invalid quantity")
    return errors


def validate_extraction(
    extraction: CommerceExtraction | SteelExtraction,
    *,
    catalog_products: set[str] | None = None,
    min_confidence: float = 0.85,
) -> list[str]:
    errors: list[str] = []
    if isinstance(extraction, SteelExtraction):
        for item in extraction.line_items:
            errors.extend(validate_steel_item(item, min_confidence=min_confidence))
    else:
        products = catalog_products or set()
        for item in extraction.line_items:
            errors.extend(
                validate_commerce_item(
                    item,
                    catalog_products=products,
                    min_confidence=min_confidence,
                )
            )
    return errors
