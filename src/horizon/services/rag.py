"""Retrieval-augmented generation index over guides + md skills (Chroma).

On startup horizon indexes every guide and md skill into an embedded Chroma
collection. Retrieval pulls the most relevant chunks for a question so the AI
assistant can ground and cite its answers in local content.

NOTE: stub for v0.1 scaffold — implemented in the RAG + AI assistant step.
"""

from __future__ import annotations


def reindex_content() -> None:
    """(Re)build the vector index from guides and md skills on disk."""
    raise NotImplementedError("Implemented in the RAG + AI assistant step.")


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """Return the most relevant content chunks for a query, with source ids."""
    raise NotImplementedError("Implemented in the RAG + AI assistant step.")
