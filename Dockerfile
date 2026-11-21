FROM python:3.12-slim
WORKDIR /srv/mimic
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY docker/apt-packages.txt /tmp/apt-packages.txt
RUN if [ -n "$(tr -d '[:space:]' < /tmp/apt-packages.txt)" ]; then \
      apt-get update \
      && xargs -r apt-get install -y --no-install-recommends < /tmp/apt-packages.txt \
      && rm -rf /var/lib/apt/lists/*; \
    fi
ARG EXTRAS=""
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev $(for e in $(echo "$EXTRAS" | tr ',' ' '); do printf -- '--extra %s ' "$e"; done)
COPY . .
ENV PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    MIMIC_MODELS_DIR=/srv/mimic/models
RUN if [ -f scripts/fetch_models.py ]; then uv run --no-sync python scripts/fetch_models.py || true; fi
EXPOSE 8501
CMD ["uv", "run", "--no-sync", "streamlit", "run", "app/main.py", "--server.address=0.0.0.0"]
