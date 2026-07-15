# AI Control Plane

A **multi-tenant AI control plane** that converts unstructured business requests into **validated, auditable actions**.

Designed for two interview/demo use cases — **commerce order extraction** and **steel RFQ extraction** — on the same platform with different schemas, policies, and knowledge bases.

> **Thesis:** AI demos are easy. The hard part is making AI trustworthy enough to trigger real business actions.

## Why this exists

| Risk domain | Commerce (caps order) | Steel procurement (RFQ) |
|-------------|----------------------|-------------------------|
| Wrong extraction | Wrong product price or payment instruction loses money | Wrong grade, norm or dimension creates procurement mistakes |
| Untrusted input | WhatsApp / chat messages | Inbound emails and attachments |
| Enterprise needs | Multi-tenant vendors | Multi-tenant buyers, EU data residency |

This repo proves: **I understand the business problem, I can build the platform, I know where AI systems fail, and I can operate them in production.**

## Control plane flow

```
Unstructured request
        ↓
Tenant and policy resolution
        ↓
RAG retrieval (tenant-filtered)
        ↓
LiteLLM gateway
        ↓
Commercial model or self-hosted vLLM
        ↓
Pydantic structured output
        ↓
Domain validation
        ↓
Evaluation and observability
        ↓
Approved business workflow
```

**The LLM proposes. The platform decides whether the result is acceptable.**

## Quick start (no API keys)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Full 10-minute interview sequence
aicp presentation

# Individual scenarios
aicp run commerce
aicp run steel
aicp run injection
aicp tenant-isolation
aicp evals
aicp costs
```

## Run it as a service (FastAPI)

```bash
uvicorn control_plane.api:app --port 8080
# interactive docs: http://localhost:8080/docs
```

| Endpoint | What it proves |
|----------|----------------|
| `POST /v1/extract` (`X-Tenant-Id` header) | Full pipeline: policy → routing → RAG → extraction → validation |
| → HTTP 403 on injection | Security gate before any model call |
| → HTTP 429 on budget exhaustion | AI FinOps enforced in the request path |
| `GET /metrics` | Prometheus counters with tenant/model/use-case labels |
| `GET /v1/costs` | Per-tenant cost attribution |
| `GET /v1/tenants/{id}/policy` | Governance: residency, provider access, budget |
| `GET /v1/evals/golden` | Golden-dataset quality gate |

Or run the container (built by CI with provenance attestation):

```bash
docker run -p 8080:8080 ghcr.io/lolupapi/ai-control-plane:latest
```

## MCP server (tenant-scoped agentic tools)

```bash
pip install -e ".[mcp]"
AICP_TENANT_ID=caps_shop_a python -m control_plane.mcp_server
```

Tenant identity is bound at **process start from the environment**, never from
model-controlled tool arguments — a prompt-injected agent cannot reach another
tenant's data. Tools expose validated platform operations (`extract_request`,
`search_knowledge`, `get_tenant_policy`), and every result carries the
platform's `workflow_action` decision.

## Two use cases, one platform

| Use case | Demo input | Tenant |
|----------|------------|--------|
| **A — Commerce** | "I need 50 black caps delivered to Lagos by Friday…" | `caps_shop_a` |
| **B — Steel RFQ** | "Please quote 20 tonnes of S355J2+N plates, EN 10025-2…" | `vanilla_steel_eu` |

Same control plane. Different Pydantic schemas, policies, retrieval sources, and evaluation datasets.

## Model routing (risk-aware)

```python
def choose_model(request):
    if request.contains_sensitive_data:
        return "local-qwen-eu"
    if request.complexity == "high":
        return "premium-extractor"
    return "small-extractor"
```

- Simple requests → smaller, cheaper model
- Complex or low-confidence → stronger model
- Sensitive tenants → self-hosted models (EU / on-prem)

## Security

Inbound channels are **untrusted data**. Prompt injection and privilege escalation are blocked **before** any model call:

```json
{
  "blocked": true,
  "reason": "Prompt injection attempt",
  "workflow_action": "human_review"
}
```

Uses `<untrusted_user_message>` wrapping and pre-model injection detection — patterns common in production agent systems.

## Tenant isolation

```python
results = vector_store.search(query=query, filters={"tenant_id": tenant_id})
```

Isolation is enforced in the retrieval query and runtime identity — **not left to the model**.

## Evaluation & FinOps

```text
Field accuracy:        94.2%
Invalid grade rate:     0.8%
Human review rate:      6.1%
Average latency:        1.8s
Average cost/request: €0.013
Regression status:     PASS
```

Every request carries tenant, use case, model, environment, and token usage.

## Optional: real LiteLLM path

```bash
pip install -e ".[llm]"
export LITELLM_BASE_URL=http://litellm.ai-platform.svc.cluster.local:4000/v1
export LITELLM_API_KEY=sk-...
aicp run commerce --mode llm
```

## Portfolio (LoluPapi — safe to share)

All repos below are **personal open-source demos**. No proprietary company code.

| Repo | Role |
|------|------|
| [ai-control-plane](https://github.com/LoluPapi/ai-control-plane) | This repo — application control plane + live demo |
| [agentic-commerce-lab](https://github.com/LoluPapi/agentic-commerce-lab) | The agent layer: tool-calling loop with production guards |
| [pulumi-ai-platform](https://github.com/LoluPapi/pulumi-ai-platform) | Pulumi components + Kubernetes deploy bundle |
| [foundry-agent-evals](https://github.com/LoluPapi/foundry-agent-evals) | Evaluations as a blocking CI gate |

## Presentation script

See [PRESENTATION.md](./PRESENTATION.md) for the minute-by-minute interview walkthrough,
and [SHEET.md](./SHEET.md) for plain-English explanations of every concept
(LiteLLM, KServe vs vLLM, MCP security, EU AI Act, FinOps, paved roads).

## Design patterns demonstrated

- `<untrusted_user_message>` envelope + injection detection → `control_plane/security.py`
- Tenant-scoped retrieval RAG → `control_plane/retrieval.py`
- OpenAI-compatible LiteLLM gateway → optional `extract_via_llm`
- Golden eval regression gate → `data/golden/` + [foundry-agent-evals](https://github.com/LoluPapi/foundry-agent-evals)

## License

MIT
