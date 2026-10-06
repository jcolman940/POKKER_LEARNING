.PHONY: setup dev bench test test-core test-backend test-frontend test-integration migrate

setup:
	cd backend && uv sync
	cd frontend && npm install

dev:
	scripts/dev.sh

bench:
	scripts/bench.sh

test:
	scripts/test.sh

test-core:
	scripts/test.sh core

test-backend:
	scripts/test.sh backend

test-frontend:
	scripts/test.sh frontend

test-integration:
	scripts/test.sh integration

migrate:
	cd backend && uv run alembic upgrade head
