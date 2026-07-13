"""Mock and optional LiteLLM-backed extractors."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from control_plane.schemas import (
    CommerceExtraction,
    CommerceLineItem,
    SteelExtraction,
    SteelLineItem,
)

if TYPE_CHECKING:
    from control_plane.retrieval import RetrievalHit


def _parse_int_after(text: str, token: str) -> int | None:
    m = re.search(rf"(\d+)\s+{re.escape(token)}", text, re.I)
    return int(m.group(1)) if m else None


def _parse_tons(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*tonnes?", text, re.I)
    return float(m.group(1)) if m else None


def _parse_dimensions(text: str) -> tuple[float, float, float] | None:
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*mm",
        text,
        re.I,
    )
    if not m:
        return None
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def extract_commerce_mock(
    text: str,
    *,
    tenant_id: str,
    retrieval_hits: list[RetrievalHit] | None = None,
) -> CommerceExtraction:
    qty = _parse_int_after(text, "black caps") or _parse_int_after(text, "caps") or 1
    city = "Lagos" if "lagos" in text.lower() else None
    deadline = "Friday" if "friday" in text.lower() else None
    return CommerceExtraction(
        tenant_id=tenant_id,
        line_items=[
            CommerceLineItem(
                product="black cap",
                color="black",
                quantity=qty,
                delivery_city=city,
                delivery_deadline=deadline,
                wants_payment_options="payment" in text.lower(),
                wants_total="total" in text.lower(),
                confidence=0.93,
            )
        ],
        notes=f"Retrieved {len(retrieval_hits or [])} catalogue chunks",
    )


def extract_steel_mock(
    text: str,
    *,
    tenant_id: str,
    retrieval_hits: list[RetrievalHit] | None = None,
) -> SteelExtraction:
    grade = "S355J2+N" if "S355" in text.upper() else "UNKNOWN"
    norm = "EN 10025-2" if "EN 10025" in text.upper() else None
    dims = _parse_dimensions(text) or (10.0, 2000.0, 6000.0)
    tons = _parse_tons(text) or 20.0
    coating = None
    lower = text.lower()
    if "shot blast" in lower and "primed" in lower:
        coating = "shot blasted and primed"
    return SteelExtraction(
        tenant_id=tenant_id,
        line_items=[
            SteelLineItem(
                grade=grade,
                norm=norm,
                thickness_mm=dims[0],
                width_mm=dims[1],
                length_mm=dims[2],
                quantity_tons=tons,
                coating=coating,
                confidence=0.91,
            )
        ],
        notes=f"Retrieved {len(retrieval_hits or [])} grade/spec chunks",
    )


def extract_via_llm(text: str, *, tenant_id: str, use_case: str, model: str):
    """Optional OpenAI-compatible path through LiteLLM gateway."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install with: pip install 'ai-control-plane[llm]'") from exc

    base_url = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000/v1")
    api_key = os.environ.get("LITELLM_API_KEY", "sk-demo")
    client = OpenAI(base_url=base_url, api_key=api_key)

    schema_hint = (
        "Return JSON for commerce line items with product, quantity, delivery_city."
        if use_case == "commerce"
        else "Return JSON for steel RFQ with grade, norm, dimensions_mm, quantity_tons, coating."
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an extraction engine. Output only valid JSON matching "
                    f"the {use_case} schema. {schema_hint}"
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    import json

    payload = json.loads(response.choices[0].message.content or "{}")
    if use_case == "commerce":
        return CommerceExtraction.model_validate({**payload, "tenant_id": tenant_id})
    return SteelExtraction.model_validate({**payload, "tenant_id": tenant_id})
