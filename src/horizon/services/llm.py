"""Local LLM client (Ollama by default; llama.cpp OpenAI-compatible optional).

Used for both answer generation and embeddings. All calls go to a local-network
endpoint; horizon degrades gracefully (the rest of the app works) if the model
runtime is unavailable.

NOTE: stub for v0.1 scaffold — implemented in the RAG + AI assistant step.
"""

from __future__ import annotations


def generate(system: str, prompt: str, *, no_jargon: bool = False) -> str:
    """Generate a completion from the local model."""
    raise NotImplementedError("Implemented in the RAG + AI assistant step.")


def embed(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for the given texts."""
    raise NotImplementedError("Implemented in the RAG + AI assistant step.")
