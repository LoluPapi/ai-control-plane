"""Tenant policy resolution and model routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Complexity(str, Enum):
    LOW = "low"
    HIGH = "high"


@dataclass(frozen=True)
class TenantPolicy:
    tenant_id: str
    use_case: str
    display_name: str
    contains_sensitive_data: bool = False
    data_residency: str = "eu"
    external_providers_allowed: bool = True
    min_confidence: float = 0.85
    human_review_on_low_confidence: bool = True
    # AI FinOps: hard monthly spend ceiling enforced at the gateway/API layer.
    monthly_budget_eur: float = 100.0


TENANT_POLICIES: dict[str, TenantPolicy] = {
    "caps_shop_a": TenantPolicy(
        tenant_id="caps_shop_a",
        use_case="commerce",
        display_name="Shop A — Cap Catalogue",
        contains_sensitive_data=False,
        external_providers_allowed=True,
        min_confidence=0.85,
    ),
    "makeup_shop_b": TenantPolicy(
        tenant_id="makeup_shop_b",
        use_case="commerce",
        display_name="Shop B — Makeup Services",
        contains_sensitive_data=False,
        external_providers_allowed=True,
        min_confidence=0.85,
    ),
    "vanilla_steel_eu": TenantPolicy(
        tenant_id="vanilla_steel_eu",
        use_case="steel",
        display_name="Vanilla Steel EU",
        contains_sensitive_data=True,
        data_residency="eu",
        external_providers_allowed=False,
        min_confidence=0.85,
        monthly_budget_eur=500.0,
    ),
    "enterprise_b": TenantPolicy(
        tenant_id="enterprise_b",
        use_case="commerce",
        display_name="Enterprise B",
        contains_sensitive_data=True,
        data_residency="eu",
        external_providers_allowed=False,
        min_confidence=0.90,
    ),
}


def resolve_policy(tenant_id: str, use_case: str) -> TenantPolicy:
    if tenant_id in TENANT_POLICIES:
        return TENANT_POLICIES[tenant_id]
    return TenantPolicy(
        tenant_id=tenant_id,
        use_case=use_case,
        display_name=tenant_id,
    )


def estimate_complexity(text: str, use_case: str) -> Complexity:
    """Heuristic complexity for routing — mirrors production signals."""
    if use_case == "steel":
        markers = ("EN ", "S355", "shot blast", "primed", "x", "tonnes", "mm")
        hits = sum(1 for m in markers if m.lower() in text.lower())
        return Complexity.HIGH if hits >= 3 else Complexity.LOW
    words = len(text.split())
    return Complexity.HIGH if words > 18 else Complexity.LOW


def choose_model(
    *,
    policy: TenantPolicy,
    complexity: Complexity,
    contains_injection: bool = False,
) -> str:
    """Risk-aware model routing. The LLM proposes; the platform decides."""
    if contains_injection:
        return "blocked"

    if policy.contains_sensitive_data or not policy.external_providers_allowed:
        return "local-qwen-eu"

    if complexity == Complexity.HIGH:
        return "premium-extractor"

    return "small-extractor"
