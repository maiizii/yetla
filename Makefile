COMPOSE = docker compose -f docker-compose.yml -f docker-compose.override.yml

.PHONY: up down logs test shell

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

test:
	$(COMPOSE) run --rm backend pytest -q

shell:
	$(COMPOSE) run --rm backend bash
