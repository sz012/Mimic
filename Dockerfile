FROM python:3.12-slim
WORKDIR /srv/mimic
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml ./
RUN uv sync --no-install-project
COPY . .
EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "app/main.py", "--server.address=0.0.0.0"]
