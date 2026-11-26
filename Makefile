.PHONY: install lint fmt test check

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check --fix .
	ruff format .

test:
	pytest -q

check: lint test
