"""Service layer.

Services isolate external dependencies (the LLM, vector DB, PDF engine) so the
Knowledge API and recommendation logic stay pure and testable without any of
them running. Only the AI assistant step requires Ollama/Chroma to be live.
"""
