# syntax=docker/dockerfile:1
FROM python:3.11-slim

# System dependencies for WeasyPrint (PDF/print mode) and general build needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY content ./content
COPY config.example.yaml ./

# Install horizon. By default this is the lean, offline-first set — the heavy
# AI vector-search stack (chromadb + onnxruntime/tokenizers/huggingface-hub/…)
# is left out, so the image is small and the build doesn't re-download hundreds
# of MB of manylinux wheels each time. Retrieval falls back to keyword search.
# To bake in vector search, build with `--build-arg INSTALL_EXTRAS=ai`.
#
# The BuildKit cache mount keeps pip's wheel cache between builds, so even a
# clean rebuild reuses already-downloaded wheels instead of fetching them again.
ARG INSTALL_EXTRAS=""
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ".${INSTALL_EXTRAS:+[$INSTALL_EXTRAS]}"

# The web UI assets ship inside the wheel (see pyproject package-data); the
# bundled seed content stays at /app/content and is located via this env var on
# first run (it is copied into the /data volume, then served from there).
ENV HORIZON_BUNDLED_CONTENT=/app/content
# Keep the node fully offline: Chroma sends anonymous usage telemetry by default.
ENV ANONYMIZED_TELEMETRY=false

# Runtime data (database, vector index, content packs) lives on a volume.
VOLUME ["/data"]
EXPOSE 8080

CMD ["uvicorn", "horizon.main:app", "--host", "0.0.0.0", "--port", "8080"]
