# StratiSell AI Control Plane

A **multi-tenant AI control plane** that converts unstructured business requests into **validated, auditable actions**.

Built from production patterns in [StratiSell](https://stratisell.com) (WhatsApp commerce for Nigerian SMEs), designed to map directly to **Vanilla Steel**-style steel RFQ ingestion — same platform, different schemas and knowledge bases.

> **Interview thesis:** AI demos are easy. The hard part is making AI trustworthy enough to trigger real business actions.

## Why this exists

| Risk domain | StratiSell | Vanilla Steel equivalent |
|-------------|------------|--------------------------|
| Wrong extraction | Wrong product price or payment instruction loses money | Wrong grade, norm or dimension creates procurement mistakes |
| Untrusted input | WhatsApp messages | Inbound emails and attachments |
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

Mirrors StratiSell's `<untrusted_user_message>` envelope and injection detection in production Go code.

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

## Companion repos

| Repo | Role |
|------|------|
| [pulumi-ai-platform](https://github.com/LoluPapi/pulumi-ai-platform) | Reusable Pulumi components + multi-cloud stacks |
| [stratiflux-gitops/platform/enterprise-ai](https://github.com/stratiflux/stratiflux-gitops/tree/main/platform/enterprise-ai) | LiteLLM + KServe GitOps bundle |
| [stratiflux-infra/azure/enterprise-ai-platform](https://github.com/stratiflux/stratiflux-infra) | Azure AKS substrate (Terraform) |
| [foundry-agent-evals](https://github.com/LoluPapi/foundry-agent-evals) | Evaluations as a blocking CI gate |

## Presentation script

See [PRESENTATION.md](./PRESENTATION.md) for the minute-by-minute interview walkthrough.

## Production lineage

Patterns ported from StratiSell production code:

- `guardrails.WrapUntrusted` / injection detection → `control_plane/security.py`
- pgvector tenant-scoped catalog RAG → `control_plane/retrieval.py`
- OpenAI-compatible LiteLLM gateway → optional `extract_via_llm`
- Eval gate philosophy → `foundry-agent-evals` + golden dataset report

## License

MIT
