.PHONY: setup run test eval ingest labels-check refresh docker api web web-build

setup:
	uv sync

run:
	uv run streamlit run app/main.py

test:
	uv run pytest

eval:
	uv run python eval/run_eval.py

ingest:
	uv run python -m scripts.ingest

labels-check:
	uv run python -m scripts.labels_check

refresh:
	uv run python -m scripts.refresh

docker:
	docker compose up --build

api:
	uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd web && npm run dev

web-build:
	cd web && npm run build
