FROM python:3.12-slim
WORKDIR /srv/mimic
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY . .
EXPOSE 8501
CMD ["uv", "run", "--frozen", "--no-dev", "streamlit", "run", "app/main.py", "--server.address=0.0.0.0"]
