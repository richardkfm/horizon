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

RUN pip install --no-cache-dir .

# The web UI assets ship inside the wheel (see pyproject package-data); the
# bundled seed content stays at /app/content and is located via this env var on
# first run (it is copied into the /data volume, then served from there).
ENV HORIZON_BUNDLED_CONTENT=/app/content

# Runtime data (database, vector index, content packs) lives on a volume.
VOLUME ["/data"]
EXPOSE 8080

CMD ["uvicorn", "horizon.main:app", "--host", "0.0.0.0", "--port", "8080"]
