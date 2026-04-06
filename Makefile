.PHONY: dev api-dev web-dev db-up db-down migrate seed lint test

dev:
	@make -j2 api-dev web-dev

api-dev:
	cd api && .venv/bin/python -m uvicorn app.main:app --reload --port 8000

web-dev:
	cd web && npm run dev

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
