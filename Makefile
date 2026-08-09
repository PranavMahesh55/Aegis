SHELL := /bin/bash
PYTHON ?= python3
VENV := .venv
API_PY := $(VENV)/bin/python
API_PIP := $(VENV)/bin/pip

.PHONY: bootstrap install-api install-datahub install-runtime install-web dev dev-api dev-web test test-api test-web lint build datahub-up datahub-down datahub-seed datahub-verify demo-up demo-online demo-down demo-reset demo-prime demo-verify clean

bootstrap: install-api install-web

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)

install-api: $(VENV)/bin/python
	$(API_PIP) install --upgrade pip
	$(API_PIP) install -e 'apps/api[dev]'

install-datahub: $(VENV)/bin/python
	@$(API_PY) -c 'import sys; raise SystemExit("DataHub runtime requires Python 3.12 or 3.13; use Docker on Python 3.14") if sys.version_info >= (3, 14) else None'
	$(API_PIP) install -e 'apps/api[datahub]'

install-runtime: $(VENV)/bin/python
	@$(API_PY) -c 'import sys; raise SystemExit("Live runtime requires Python 3.12 or 3.13; use Docker on Python 3.14") if sys.version_info >= (3, 14) else None'
	$(API_PIP) install -e 'apps/api[runtime]'

install-web:
	npm --prefix apps/web install

dev:
	@trap 'kill 0' EXIT; $(MAKE) dev-api & $(MAKE) dev-web & wait

dev-api:
	$(API_PY) -m uvicorn aegis.main:app --app-dir apps/api --reload --port 8000

dev-web:
	npm --prefix apps/web run dev -- --host 0.0.0.0

test: test-api test-web

test-api:
	$(API_PY) -m pytest apps/api/tests -q

test-web:
	npm --prefix apps/web test -- --run

lint:
	$(VENV)/bin/ruff check apps/api
	npm --prefix apps/web run typecheck

build:
	npm --prefix apps/web run build
	$(API_PY) -m compileall -q apps/api/aegis

datahub-up:
	$(VENV)/bin/datahub docker quickstart --version v1.7.0

datahub-down:
	$(VENV)/bin/datahub docker quickstart --stop

datahub-seed:
	$(API_PY) scripts/datahub/seed.py

datahub-verify:
	$(API_PY) scripts/datahub/verify.py

demo-up:
	docker compose up --build -d

demo-online:
	docker compose --profile online up --build -d

demo-down:
	docker compose down

demo-reset:
	curl -fsS -X POST http://localhost:8000/api/demo/reset -H 'Content-Type: application/json' -d '{"target":"HEALTHY_BASELINE"}' | $(PYTHON) -m json.tool

demo-prime:
	curl -fsS -X POST http://localhost:8000/api/demo/prime -H 'Content-Type: application/json' -d '{}' | $(PYTHON) -m json.tool

demo-verify:
	curl -fsS http://localhost:8000/api/system/status | $(PYTHON) -m json.tool

clean:
	rm -rf apps/web/dist apps/web/node_modules .venv .pytest_cache
