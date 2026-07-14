# Architecture

> **Design thesis:** AI demos are easy. The hard part is making AI trustworthy enough
> to trigger real business actions. The LLM proposes; the platform decides.

## High-level architecture

```mermaid
flowchart LR
    subgraph inbound["Untrusted inbound"]
        E["Email / chat / documents<br/>(attacker-controlled)"]
    end

    subgraph cp["AI Control Plane"]
        direction TB
        SEC["Security gate<br/><i>injection screening, envelope wrapping</i>"]
        POL["Tenant policy<br/><i>residency · budget · providers</i>"]
        RAG["Tenant-scoped retrieval<br/><i>filter enforced in query</i>"]
        VAL["Domain validation<br/><i>grade book · catalogue · confidence</i>"]
    end

    subgraph gw["LiteLLM gateway"]
        RT["Routing · aliases · fallbacks<br/>budgets · cost tags"]
    end

    subgraph models["Model plane"]
        EXT["Commercial APIs<br/><i>premium-extractor</i>"]
        VLLM["KServe + vLLM<br/><i>local-qwen-eu, self-hosted</i>"]
    end

    subgraph out["Governed output"]
        WF["Approved workflow<br/>or human review"]
        OBS["Prometheus · evals · audit trail"]
    end

    E --> SEC --> POL --> RAG --> RT
    RT --> EXT & VLLM
    EXT & VLLM --> VAL --> WF
    VAL -.-> OBS
    RT -.-> OBS

    style SEC fill:#7f1d1d,stroke:#f87171,color:#fff
    style POL fill:#1e3a8a,stroke:#5b8cff,color:#fff
    style RAG fill:#1e3a8a,stroke:#5b8cff,color:#fff
    style VAL fill:#14532d,stroke:#34d399,color:#fff
    style RT fill:#3b2f0e,stroke:#fbbf24,color:#fff
    style VLLM fill:#312e81,stroke:#818cf8,color:#fff
```

## One request, end to end

```mermaid
sequenceDiagram
    autonumber
    participant C as Inbound request<br/>(untrusted)
    participant API as Control plane API<br/>(FastAPI)
    participant P as Policy engine
    participant V as Vector store<br/>(tenant-filtered)
    participant G as LiteLLM gateway
    participant M as Model<br/>(vLLM / commercial)
    participant D as Domain validation

    C->>API: POST /v1/extract + X-Tenant-Id
    API->>API: Security screen (injection?)
    alt injection detected
        API-->>C: 403 blocked · human_review<br/>(zero tokens spent)
    end
    API->>P: resolve tenant policy
    P-->>API: residency, budget, min_confidence
    alt budget exhausted
        API-->>C: 429 finops_review
    end
    API->>V: search(query, tenant_id=X)
    V-->>API: tenant-scoped knowledge only
    API->>G: chat.completions (model chosen by risk)
    G->>M: route to alias
    M-->>G: raw extraction
    G-->>API: structured candidate
    API->>D: validate (grades, dimensions, confidence)
    D-->>API: errors [] or human_review
    API-->>C: extraction + workflow_action + cost
    API--)API: record metrics (tenant, model, tokens, EUR)
```

## Risk-based model routing

```mermaid
flowchart TD
    R[Request] --> Q1{Injection<br/>detected?}
    Q1 -- yes --> B["BLOCKED<br/>human_review, 0 tokens"]
    Q1 -- no --> Q2{"Sensitive tenant /<br/>external providers<br/>forbidden?"}
    Q2 -- yes --> L["local-qwen-eu<br/><i>self-hosted vLLM, EU</i>"]
    Q2 -- no --> Q3{Complexity?}
    Q3 -- high --> P["premium-extractor<br/><i>stronger commercial model</i>"]
    Q3 -- low --> S["small-extractor<br/><i>cheap, fast default</i>"]

    style B fill:#7f1d1d,stroke:#f87171,color:#fff
    style L fill:#312e81,stroke:#818cf8,color:#fff
    style P fill:#3b2f0e,stroke:#fbbf24,color:#fff
    style S fill:#14532d,stroke:#34d399,color:#fff
```

Simple requests default to the cheapest model; sensitivity overrides everything.
Residency is a **policy flag, not a fork** of the platform.

## Tenant isolation model

```mermaid
flowchart LR
    subgraph tA["Tenant A (e.g. OEM buyer)"]
        KA["Knowledge base A<br/>prices · suppliers · specs"]
    end
    subgraph tB["Tenant B (competitor)"]
        KB["Knowledge base B"]
    end

    AG["Agent / API caller<br/>runtime identity: tenant A"] -->|"search(query, tenant_id=A)"| F{"Filter enforced<br/>in the query"}
    F -->|allowed| KA
    F -.->|"unreachable<br/>(not a prompt rule)"| KB

    style F fill:#7f1d1d,stroke:#f87171,color:#fff
    style KB fill:#1a2036,stroke:#232d4a,color:#8b96b8
```

Tenants may be **competitors of each other**. Isolation is enforced in the
retrieval filter and the runtime identity (the MCP server binds its tenant at
process start from the environment) — never delegated to model behavior.

## Deployment topology

```mermaid
flowchart TB
    subgraph iac["pulumi-ai-platform (one component library)"]
        COMP["AiPlatform component<br/><i>capability flags</i>"]
    end

    COMP --> S1["saas-gcp<br/>external + self-hosted"]
    COMP --> S2["customer-aws<br/>EU residency, GPU"]
    COMP --> S3["customer-azure<br/>locked to self-hosted"]
    COMP --> S4["customer-onprem<br/>air-gapped"]

    subgraph runtime["Each environment runs the same plane"]
        API2["control-plane-api<br/><i>ghcr image, provenance-attested</i>"]
        LL["LiteLLM"]
        KS["KServe / vLLM"]
        API2 --> LL --> KS
    end

    S1 & S2 & S3 & S4 -.-> runtime

    style COMP fill:#1e3a8a,stroke:#5b8cff,color:#fff
```

Four environments, one component, capability flags — **not four platforms**.

## The audit trail (what enterprise customers buy)

Every request emits, atomically:

| Field | Why an auditor cares |
|-------|----------------------|
| `tenant` | Whose data, whose budget, whose policy |
| `model` + gateway alias | Which system produced the proposal |
| `workflow_action` | The platform's decision (approve / human_review / blocked) |
| `validation_errors` | Why the platform doubted the model |
| token usage + `cost_eur` | FinOps attribution in the request path |
| latency | SLO evidence |

This is the evidence chain for ISO 27001 / EU AI Act conversations — and the
Prometheus labels double as the Grafana dashboard dimensions.
