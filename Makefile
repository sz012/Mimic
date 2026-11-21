.PHONY: setup run test eval ingest labels-check docker

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

docker:
	docker compose up --build
