-include .env
export

UV ?= uv
HOST ?= 127.0.0.1
PORT ?= 8000
DATA_DIR ?= .manim-server-data
TEMPLATE_DIR ?= template
MANIM_CLI_FLAGS ?= -ql
MANIM_TIMEOUT_SECONDS ?= 120
PYTEST_ARGS ?= -q
TY_ARGS ?= app tests
IMAGE ?= manim-server
CONTAINER ?= manim-server-smoke

.PHONY: sync test lint format typecheck build run smoke docker-build docker-run docker-smoke

sync:
	$(UV) sync --all-groups

lint:
	$(UV) run ruff check $(TY_ARGS) --fix

format:
	$(UV) run ruff format $(TY_ARGS)

typecheck:
	$(UV) run ty check $(TY_ARGS)

test: lint format typecheck
	$(UV) run pytest $(PYTEST_ARGS)

build: test
	$(UV) build

run:
	$(UV) run uvicorn app.main:app --host $(HOST) --port $(PORT)

smoke:
	$(UV) run python -c "from app.main import create_app; app = create_app(); print(app.title)"

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	mkdir -p $(DATA_DIR) $(TEMPLATE_DIR)
	docker rm -f manim-server >/dev/null 2>&1 || true
	docker run --name manim-server --rm -d -p $(PORT):8000 -e DATA_DIR=/data -e TEMPLATE_DIR=/template -e MANIM_CLI_FLAGS=$(MANIM_CLI_FLAGS) -v "$(CURDIR)/$(DATA_DIR):/data" -v "$(CURDIR)/$(TEMPLATE_DIR):/template" $(IMAGE)

docker-smoke: docker-build
	docker rm -f $(CONTAINER) >/dev/null 2>&1 || true
	docker run --rm $(IMAGE) manim --version
	docker run --rm -d --name $(CONTAINER) -p $(PORT):8000 $(IMAGE)
	sleep 5
	curl -fsS http://127.0.0.1:$(PORT)/health
	docker rm -f $(CONTAINER) >/dev/null
