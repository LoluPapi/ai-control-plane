"""End-to-end control plane orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from control_plane.extractors import extract_commerce_mock, extract_steel_mock, extract_via_llm
from control_plane.observability import MetricsStore, RequestMetrics, Timer, estimate_cost
from control_plane.paths import data_root
from control_plane.policies import (
    Complexity,
    choose_model,
    estimate_complexity,
    resolve_policy,
)
from control_plane.retrieval import TenantVectorStore
from control_plane.schemas import CommerceExtraction, SteelExtraction
from control_plane.security import SecurityDecision, assess_inbound, wrap_untrusted
from control_plane.validation import validate_extraction

DATA_ROOT = data_root()


@dataclass
class PipelineResult:
    blocked: bool = False
    reason: str | None = None
    workflow_action: str = "approve"
    tenant_id: str = ""
    use_case: str = ""
    model: str = ""
    wrapped_input: str = ""
    retrieval_hits: list = field(default_factory=list)
    extraction: CommerceExtraction | SteelExtraction | None = None
    validation_errors: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    cost_eur: float = 0.0


def _catalog_products(tenant_id: str) -> set[str]:
    path = DATA_ROOT / "knowledge" / "caps_catalog.json"
    payload = json.loads(path.read_text())
    if payload["tenant_id"] != tenant_id:
        return set()
    return {e["content"].lower() for e in payload.get("entries", [])}


class ControlPlane:
    def __init__(
        self,
        *,
        mode: str = "mock",
        store: TenantVectorStore | None = None,
        metrics: MetricsStore | None = None,
    ) -> None:
        self.mode = mode
        self.store = store or TenantVectorStore()
        self.metrics = metrics or MetricsStore()

    def process(
        self,
        text: str,
        *,
        tenant_id: str,
        use_case: str,
    ) -> PipelineResult:
        policy = resolve_policy(tenant_id, use_case)
        security: SecurityDecision = assess_inbound(text)
        complexity = estimate_complexity(text, use_case)
        model = choose_model(
            policy=policy,
            complexity=complexity,
            contains_injection=security.blocked,
        )

        result = PipelineResult(
            tenant_id=tenant_id,
            use_case=use_case,
            model=model,
            wrapped_input=wrap_untrusted(text),
        )

        if security.blocked:
            result.blocked = True
            result.reason = security.reason
            result.workflow_action = security.workflow_action
            self.metrics.record(
                RequestMetrics(
                    tenant_id=tenant_id,
                    use_case=use_case,
                    model="blocked",
                    latency_ms=0,
                    blocked=True,
                    workflow_action=security.workflow_action,
                )
            )
            return result

        with Timer() as timer:
            hits = self.store.search(query=text, tenant_id=tenant_id)
            result.retrieval_hits = hits

            if self.mode == "llm":
                extraction = extract_via_llm(
                    text,
                    tenant_id=tenant_id,
                    use_case=use_case,
                    model=model,
                )
            elif use_case == "steel":
                extraction = extract_steel_mock(text, tenant_id=tenant_id, retrieval_hits=hits)
            else:
                extraction = extract_commerce_mock(text, tenant_id=tenant_id, retrieval_hits=hits)

            catalog = _catalog_products(tenant_id) if use_case == "commerce" else None
            errors = validate_extraction(
                extraction,
                catalog_products=catalog,
                min_confidence=policy.min_confidence,
            )

        input_tokens = max(80, len(text.split()) * 2)
        output_tokens = 120 if complexity == Complexity.HIGH else 60
        cost = estimate_cost(model, input_tokens=input_tokens, output_tokens=output_tokens)

        if errors and policy.human_review_on_low_confidence:
            workflow = "human_review"
        else:
            workflow = "approve"

        result.extraction = extraction
        result.validation_errors = errors
        result.workflow_action = workflow
        result.latency_ms = timer.elapsed_ms
        result.cost_eur = cost

        self.metrics.record(
            RequestMetrics(
                tenant_id=tenant_id,
                use_case=use_case,
                model=model,
                latency_ms=timer.elapsed_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_eur=cost,
                validation_errors=errors,
                workflow_action=workflow,
            )
        )
        return result
