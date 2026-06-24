-include .env
export

UV ?= uv
HOST ?= 127.0.0.1
PORT ?= 8000
DATA_DIR ?= .manim-server-data
MANIM_CLI_FLAGS ?= -ql
MANIM_TIMEOUT_SECONDS ?= 120
PYTEST_ARGS ?= -q
TY_ARGS ?= app tests

.PHONY: sync test typecheck build run smoke

sync:
	$(UV) sync --all-groups

test:
	$(UV) run pytest $(PYTEST_ARGS)

typecheck:
	$(UV) run ty check $(TY_ARGS)

build: typecheck test
	$(UV) build

run:
	$(UV) run uvicorn app.main:app --host $(HOST) --port $(PORT)

smoke:
	$(UV) run python -c "from app.main import create_app; app = create_app(); print(app.title)"
