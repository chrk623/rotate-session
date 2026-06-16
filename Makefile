.PHONY: lint format

lint:
	uv run ruff format .
	uv run ruff check --fix .

check:
	uv run ruff check .

format:
	uv run ruff format .

build:
	uv build --no-sources

publish:
	rm -rf dist/
	uv build --no-sources
	uv publish