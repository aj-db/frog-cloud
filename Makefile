.PHONY: dev dev-local dev-side-by-side dev-status dev-stop dev-reset repo-hygiene api-dev web-dev web-dev-local web-dev-staging db-up db-down migrate seed lint test

dev:
	@make -j2 api-dev web-dev-local

dev-local:
	@make -j2 api-dev web-dev-local

dev-side-by-side:
	@make -j3 api-dev web-dev-local web-dev-staging

api-dev:
	cd api && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

web-dev: web-dev-local

web-dev-local:
	cd web && npm run dev

web-dev-staging:
	cd web && npm run dev:staging

dev-status:
	@for spec in "8000 api" "3001 web-local" "3002 web-staging"; do \
		set -- $$spec; \
		if python3 -c "import socket; socket.create_connection(('localhost', $$1), 0.3).close()"; then \
			echo "$$2: http://localhost:$$1 (up)"; \
		else \
			echo "$$2: http://localhost:$$1 (down)"; \
		fi; \
	done

dev-stop:
	@python3 scripts/dev_cleanup.py

dev-reset:
	@python3 scripts/dev_cleanup.py --reset

repo-hygiene:
	@python3 scripts/dev_cleanup.py --git-gc

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	cd api && .venv/bin/python -m alembic upgrade head

migration:
	cd api && .venv/bin/python -m alembic revision --autogenerate -m "$(msg)"

seed:
	cd api && .venv/bin/python -m app.seed

lint:
	cd api && .venv/bin/python -m ruff check .
	cd web && npm run lint

test:
	cd api && .venv/bin/python -m pytest
	cd web && npm test

setup:
	cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd web && npm install
	cp -n .env.example .env || true
