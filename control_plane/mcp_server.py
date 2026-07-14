"""MCP server — tenant-scoped agentic tool access to the control plane.

MCP servers are a security-sensitive surface: an agent connecting to this
server can only act as ONE tenant, fixed at process start. The tenant
identity comes from the runtime environment (AICP_TENANT_ID), never from
the model's tool arguments — so a prompt-injected agent cannot ask for
another tenant's data.

Run (stdio transport, e.g. from Claude Desktop / Cursor):
    AICP_TENANT_ID=caps_shop_a python -m control_plane.mcp_server

Requires: pip install "ai-control-plane[mcp]"
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from control_plane.pipeline import ControlPlane
from control_plane.policies import resolve_policy
from control_plane.retrieval import TenantVectorStore

# Tenant identity is bound at startup from the environment — runtime identity,
# not model-controlled input. This is the isolation boundary.
TENANT_ID = os.environ.get("AICP_TENANT_ID", "caps_shop_a")
USE_CASE = os.environ.get("AICP_USE_CASE", "commerce")

mcp = FastMCP(
    "ai-control-plane",
    instructions=(
        f"Extraction and knowledge tools scoped to tenant '{TENANT_ID}'. "
        "All results are validated by the platform before any business action."
    ),
)

_plane = ControlPlane(mode=os.environ.get("AICP_MODE", "mock"))
_store = TenantVectorStore()


@mcp.tool()
def extract_request(text: str) -> dict:
    """Extract a structured, validated line item from an unstructured business request.

    The result includes a workflow_action: 'approve' means safe to act on,
    'human_review' means the platform rejected or doubted the extraction.
    """
    result = _plane.process(text, tenant_id=TENANT_ID, use_case=USE_CASE)
    if result.blocked:
        return {
            "blocked": True,
            "reason": result.reason,
            "workflow_action": result.workflow_action,
        }
    return {
        "extraction": result.extraction.model_dump() if result.extraction else None,
        "validation_errors": result.validation_errors,
        "workflow_action": result.workflow_action,
        "model": result.model,
        "cost_eur": round(result.cost_eur, 6),
    }


@mcp.tool()
def search_knowledge(query: str) -> list[dict]:
    """Search this tenant's knowledge base. Results are hard-filtered to the
    tenant bound at server start — other tenants' data is unreachable."""
    hits = _store.search(query=query, tenant_id=TENANT_ID)
    return [{"source": h.source, "content": h.content, "score": h.score} for h in hits]


@mcp.tool()
def get_tenant_policy() -> dict:
    """Show the effective governance policy for this tenant (residency, budget, thresholds)."""
    policy = resolve_policy(TENANT_ID, USE_CASE)
    return {
        "tenant_id": policy.tenant_id,
        "data_residency": policy.data_residency,
        "external_providers_allowed": policy.external_providers_allowed,
        "min_confidence": policy.min_confidence,
        "monthly_budget_eur": policy.monthly_budget_eur,
    }


if __name__ == "__main__":
    mcp.run()
