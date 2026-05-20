# Dev tasks. Uses podman by default (Docker is also fine if PODMAN=docker).

PODMAN        ?= podman
DB_CONTAINER  := payroll-postgres
DB_IMAGE      := docker.io/postgres:16-alpine
DB_USER       ?= payroll
DB_PASSWORD   ?= payroll
DB_NAME       ?= payroll
DB_PORT       ?= 5432

.PHONY: help install db-up db-down db-shell db-logs run migrate makemigrations \
        shell test lint format check tailwind-watch tailwind-build clean generate-key

help:
	@echo "Targets:"
	@echo "  install         Install Python deps via uv"
	@echo "  db-up           Start local Postgres in a container"
	@echo "  db-down         Stop and remove the Postgres container (data volume preserved)"
	@echo "  db-shell        psql into the running Postgres container"
	@echo "  db-logs         Tail Postgres logs"
	@echo "  run             Start the Django dev server"
	@echo "  migrate         Apply migrations"
	@echo "  makemigrations  Generate migrations"
	@echo "  shell           Django shell"
	@echo "  test            Run pytest"
	@echo "  lint            Run ruff and mypy"
	@echo "  format          Run ruff format and ruff --fix"
	@echo "  check           Run django manage.py check"
	@echo "  tailwind-watch  Watch and rebuild static/css/output.css"
	@echo "  tailwind-build  One-shot minified build of output.css"

install:
	uv sync

db-up:
	$(PODMAN) run -d --name $(DB_CONTAINER) \
		-e POSTGRES_USER=$(DB_USER) \
		-e POSTGRES_PASSWORD=$(DB_PASSWORD) \
		-e POSTGRES_DB=$(DB_NAME) \
		-p $(DB_PORT):5432 \
		-v $(DB_CONTAINER)-data:/var/lib/postgresql/data \
		$(DB_IMAGE)

db-down:
	-$(PODMAN) stop $(DB_CONTAINER)
	-$(PODMAN) rm $(DB_CONTAINER)

db-shell:
	$(PODMAN) exec -it $(DB_CONTAINER) psql -U $(DB_USER) -d $(DB_NAME)

db-logs:
	$(PODMAN) logs -f $(DB_CONTAINER)

run:
	uv run python manage.py runserver

migrate:
	uv run python manage.py migrate

makemigrations:
	uv run python manage.py makemigrations

shell:
	uv run python manage.py shell

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run mypy .

format:
	uv run ruff format .
	uv run ruff check --fix .

check:
	uv run python manage.py check

tailwind-watch:
	./bin/tailwindcss -i static/src/input.css -o static/css/output.css --watch

tailwind-build:
	./bin/tailwindcss -i static/src/input.css -o static/css/output.css --minify

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +

generate-key:
	@uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
