"""Cost, latency, and evaluation observability."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from control_plane.paths import data_root

DATA_ROOT = data_root()

MODEL_COST_PER_1K: dict[str, float] = {
    "small-extractor": 0.0008,
    "premium-extractor": 0.0045,
    "local-qwen-eu": 0.0,
    "blocked": 0.0,
}


@dataclass
class RequestMetrics:
    tenant_id: str
    use_case: str
    model: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_eur: float = 0.0
    blocked: bool = False
    validation_errors: list[str] = field(default_factory=list)
    workflow_action: str = "approve"


class MetricsStore:
    def __init__(self) -> None:
        self._requests: list[RequestMetrics] = []

    def record(self, metric: RequestMetrics) -> None:
        self._requests.append(metric)

    def tenant_cost(self, tenant_id: str) -> float:
        return sum(r.cost_eur for r in self._requests if r.tenant_id == tenant_id)

    def render_prometheus(self) -> str:
        """Prometheus text exposition — every request carries tenant, use case, model."""
        counters: dict[tuple[str, str, str, str], int] = {}
        costs: dict[str, float] = {}
        latencies: dict[str, list[float]] = {}
        for r in self._requests:
            key = (r.tenant_id, r.use_case, r.model, r.workflow_action)
            counters[key] = counters.get(key, 0) + 1
            costs[r.tenant_id] = costs.get(r.tenant_id, 0.0) + r.cost_eur
            latencies.setdefault(r.tenant_id, []).append(r.latency_ms)

        lines = [
            "# HELP aicp_requests_total Requests processed by the control plane.",
            "# TYPE aicp_requests_total counter",
        ]
        for (tenant, use_case, model, action), count in sorted(counters.items()):
            lines.append(
                f'aicp_requests_total{{tenant="{tenant}",use_case="{use_case}",'
                f'model="{model}",workflow_action="{action}"}} {count}'
            )
        lines += [
            "# HELP aicp_cost_eur_total Cumulative cost per tenant in EUR.",
            "# TYPE aicp_cost_eur_total counter",
        ]
        for tenant, cost in sorted(costs.items()):
            lines.append(f'aicp_cost_eur_total{{tenant="{tenant}"}} {cost:.6f}')
        lines += [
            "# HELP aicp_latency_ms_avg Average request latency per tenant.",
            "# TYPE aicp_latency_ms_avg gauge",
        ]
        for tenant, vals in sorted(latencies.items()):
            avg = sum(vals) / len(vals) if vals else 0.0
            lines.append(f'aicp_latency_ms_avg{{tenant="{tenant}"}} {avg:.3f}')
        return "\n".join(lines) + "\n"

    def tenant_summary(self) -> list[dict]:
        by_tenant: dict[str, dict] = {}
        for r in self._requests:
            bucket = by_tenant.setdefault(
                r.tenant_id,
                {"tenant": r.tenant_id, "requests": 0, "cost_eur": 0.0},
            )
            bucket["requests"] += 1
            bucket["cost_eur"] += r.cost_eur
        rows = []
        for t, b in sorted(by_tenant.items()):
            avg = b["cost_eur"] / b["requests"] if b["requests"] else 0.0
            rows.append(
                {
                    "tenant": t,
                    "requests": b["requests"],
                    "cost_eur": round(b["cost_eur"], 4),
                    "avg_request_eur": round(avg, 4),
                }
            )
        return rows


def estimate_cost(model: str, *, input_tokens: int, output_tokens: int) -> float:
    rate = MODEL_COST_PER_1K.get(model, 0.001)
    return ((input_tokens + output_tokens) / 1000.0) * rate


@dataclass
class EvalReport:
    field_accuracy: float
    invalid_grade_rate: float
    human_review_rate: float
    avg_latency_s: float
    avg_cost_eur: float
    regression_status: str


def load_golden_report(path: Path | None = None) -> EvalReport:
    """Pre-computed golden dataset results for presentation."""
    payload = json.loads((path or DATA_ROOT / "golden" / "report.json").read_text())
    return EvalReport(**payload)


class Timer:
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
