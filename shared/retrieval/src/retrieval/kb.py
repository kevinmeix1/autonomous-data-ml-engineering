from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    doc_id: str
    title: str
    content: str
    score: float
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBase:
    """Lightweight keyword RAG over markdown/text knowledge docs.

    Avoids heavy embedding deps at import time; uses token overlap scoring.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or "knowledge-base")
        self.docs: list[RetrievedChunk] = []
        if self.root.exists():
            self.index()

    def index(self) -> int:
        self.docs.clear()
        for path in self.root.rglob("*"):
            if path.suffix.lower() not in {".md", ".txt", ".yaml", ".yml"}:
                continue
            text = path.read_text(errors="ignore")
            self.docs.append(
                RetrievedChunk(
                    doc_id=str(path.relative_to(self.root)),
                    title=path.stem.replace("_", " ").title(),
                    content=text,
                    score=0.0,
                    path=str(path),
                )
            )
        return len(self.docs)

    def search(self, query: str, *, limit: int = 5) -> list[RetrievedChunk]:
        tokens = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[RetrievedChunk] = []
        for doc in self.docs:
            hay = f"{doc.title}\n{doc.content}".lower()
            overlap = sum(1 for t in tokens if t in hay)
            if overlap:
                scored.append(doc.model_copy(update={"score": float(overlap)}))
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:limit]
