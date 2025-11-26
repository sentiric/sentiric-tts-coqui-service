.PHONY: build up down logs clean test run-local

# Modern Docker versiyonlarında "docker-compose" yerine "docker compose" kullanılır.
DOCKER_COMPOSE = docker compose

build:
	$(DOCKER_COMPOSE) build

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

run-local:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000