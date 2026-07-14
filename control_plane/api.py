"""FastAPI service — the control plane as a multi-tenant HTTP API.

Run locally:
    uvicorn control_plane.api:app --reload --port 8080

Interactive docs at http://localhost:8080/docs
"""

from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from control_plane import __version__
from control_plane.observability import MetricsStore, load_golden_report
from control_plane.pipeline import ControlPlane
from control_plane.policies import resolve_policy

app = FastAPI(
    title="AI Control Plane",
    version=__version__,
    description=(
        "Multi-tenant AI control plane: unstructured business requests in, "
        "validated structured actions out. The LLM proposes; the platform decides."
    ),
)

metrics = MetricsStore()
plane = ControlPlane(mode=os.environ.get("AICP_MODE", "mock"), metrics=metrics)


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000, description="Raw inbound request text")
    use_case: Literal["commerce", "steel"] = Field(description="Which extraction schema to apply")


class ExtractResponse(BaseModel):
    tenant_id: str
    use_case: str
    model: str
    workflow_action: str
    extraction: dict | None
    validation_errors: list[str]
    latency_ms: float
    cost_eur: float


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    return {"status": "ok", "mode": plane.mode, "version": __version__}


@app.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
def prometheus_metrics() -> str:
    """Prometheus scrape endpoint — cost, latency, and request counters per tenant."""
    return metrics.render_prometheus()


@app.post("/v1/extract", response_model=ExtractResponse, tags=["extraction"], responses={
    403: {"description": "Blocked by security gate (prompt injection / escalation)"},
    429: {"description": "Tenant monthly budget exhausted"},
})
def extract(
    body: ExtractRequest,
    x_tenant_id: str = Header(description="Tenant identity — resolved to policy, budget, and residency"),
):
    """Run one request through the full pipeline: policy → routing → RAG → extraction → validation."""
    policy = resolve_policy(x_tenant_id, body.use_case)

    # AI FinOps: per-tenant budget enforced in the request path, not in a monthly report.
    spent = metrics.tenant_cost(x_tenant_id)
    if spent >= policy.monthly_budget_eur:
        return JSONResponse(
            status_code=429,
            content={
                "error": "budget_exhausted",
                "tenant_id": x_tenant_id,
                "spent_eur": round(spent, 4),
                "monthly_budget_eur": policy.monthly_budget_eur,
                "workflow_action": "finops_review",
            },
        )

    result = plane.process(body.text, tenant_id=x_tenant_id, use_case=body.use_case)

    if result.blocked:
        return JSONResponse(
            status_code=403,
            content={
                "blocked": True,
                "reason": result.reason,
                "workflow_action": result.workflow_action,
                "tenant_id": x_tenant_id,
            },
        )

    return ExtractResponse(
        tenant_id=result.tenant_id,
        use_case=result.use_case,
        model=result.model,
        workflow_action=result.workflow_action,
        extraction=result.extraction.model_dump() if result.extraction else None,
        validation_errors=result.validation_errors,
        latency_ms=round(result.latency_ms, 2),
        cost_eur=round(result.cost_eur, 6),
    )


@app.get("/v1/tenants/{tenant_id}/policy", tags=["governance"])
def tenant_policy(tenant_id: str, use_case: str = "commerce") -> dict:
    """Effective policy for a tenant — residency, provider access, budget, thresholds."""
    policy = resolve_policy(tenant_id, use_case)
    return {
        "tenant_id": policy.tenant_id,
        "display_name": policy.display_name,
        "data_residency": policy.data_residency,
        "external_providers_allowed": policy.external_providers_allowed,
        "contains_sensitive_data": policy.contains_sensitive_data,
        "min_confidence": policy.min_confidence,
        "monthly_budget_eur": policy.monthly_budget_eur,
    }


@app.get("/v1/costs", tags=["finops"])
def costs() -> dict:
    """Per-tenant cost attribution from live request history."""
    return {"tenants": metrics.tenant_summary()}


@app.get("/v1/evals/golden", tags=["evaluation"])
def golden_report() -> dict:
    """Latest golden-dataset regression results — the quality gate."""
    report = load_golden_report()
    return {
        "field_accuracy": report.field_accuracy,
        "invalid_grade_rate": report.invalid_grade_rate,
        "human_review_rate": report.human_review_rate,
        "avg_latency_s": report.avg_latency_s,
        "avg_cost_eur": report.avg_cost_eur,
        "regression_status": report.regression_status,
    }


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "internal", "detail": str(exc)})
