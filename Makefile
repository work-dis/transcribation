PYTHON?=python3
install:; pip install -e '.[dev]'
dev:; uvicorn apps.api.main:app --reload
up:; docker compose up --build
down:; docker compose down
logs:; docker compose logs -f
migrate:; alembic upgrade head
lint:; ruff check src apps tests
format:; ruff format src apps tests
typecheck:; mypy src
test:; pytest -q
verify: lint typecheck test
