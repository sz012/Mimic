.PHONY: setup run test eval ingest labels-check refresh docker

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
