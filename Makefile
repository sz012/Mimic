.PHONY: setup run test eval docker

setup:
	uv sync

run:
	uv run streamlit run app/main.py

test:
	uv run pytest

eval:
	uv run python eval/run_eval.py

docker:
	docker compose up --build
