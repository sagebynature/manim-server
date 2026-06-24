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
IMAGE ?= manim-server
CONTAINER ?= manim-server-smoke

.PHONY: sync test typecheck build run smoke docker-build docker-run docker-smoke

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

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	mkdir -p $(DATA_DIR)
	docker run --rm -p $(PORT):8000 -e DATA_DIR=/data -v "$(CURDIR)/$(DATA_DIR):/data" $(IMAGE)

docker-smoke: docker-build
	docker rm -f $(CONTAINER) >/dev/null 2>&1 || true
	docker run --rm $(IMAGE) manim --version
	docker run --rm -d --name $(CONTAINER) -p $(PORT):8000 $(IMAGE)
	sleep 5
	curl -fsS http://127.0.0.1:$(PORT)/health
	docker rm -f $(CONTAINER) >/dev/null
