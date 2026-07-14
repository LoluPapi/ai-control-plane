"""Tenant-isolated retrieval — filters enforced in the query, not left to the model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from control_plane.paths import data_root

DATA_ROOT = data_root()


@dataclass(frozen=True)
class RetrievalHit:
    tenant_id: str
    source: str
    content: str
    score: float


class TenantVectorStore:
    """In-memory stand-in for pgvector / Weaviate with mandatory tenant filters."""

    def __init__(self, root: Path = DATA_ROOT / "knowledge") -> None:
        self._docs: list[dict] = []
        for path in sorted(root.glob("*.json")):
            payload = json.loads(path.read_text())
            tenant_id = payload.get("tenant_id")
            if not tenant_id:
                continue
            for entry in payload.get("entries", []):
                self._docs.append(
                    {
                        "tenant_id": tenant_id,
                        "source": entry.get("source", path.name),
                        "content": entry["content"],
                        "keywords": [k.lower() for k in entry.get("keywords", [])],
                    }
                )

    def search(
        self,
        *,
        query: str,
        tenant_id: str,
        top_k: int = 5,
    ) -> list[RetrievalHit]:
        """Tenant isolation is enforced in the retrieval query and runtime identity."""
        q = query.lower()
        scored: list[RetrievalHit] = []
        for doc in self._docs:
            if doc["tenant_id"] != tenant_id:
                continue
            score = 0.0
            for kw in doc["keywords"]:
                if kw in q:
                    score += 1.0
            if score > 0:
                scored.append(
                    RetrievalHit(
                        tenant_id=tenant_id,
                        source=doc["source"],
                        content=doc["content"],
                        score=score,
                    )
                )
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]
