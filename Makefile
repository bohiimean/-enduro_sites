.DEFAULT_GOAL := help
DC := docker compose

.env:
	cp .env.example .env
	@echo "Создан .env из .env.example — проверьте значения."

help:           ## Список команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: .env        ## Поднять весь стек
	$(DC) up -d --build

rates: .env     ## Поднять сервис курсов (отдельный профиль)
	$(DC) --profile rates up -d --build rates

quotes:         ## Разово обновить котировки
	$(DC) exec worker python -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from pricing.services import fetch_quotes; print('новых:', fetch_quotes())"

down:           ## Остановить
	$(DC) down

logs:           ## Логи всех сервисов
	$(DC) logs -f --tail=100

ps:             ## Состояние сервисов
	$(DC) ps

migrate:        ## Применить миграции
	$(DC) exec backend python manage.py migrate

makemigrations: ## Сгенерировать миграции
	$(DC) exec backend python manage.py makemigrations

superuser:      ## Создать администратора
	$(DC) exec backend python manage.py createsuperuser

seed:           ## Заполнить справочники и демо-данные
	$(DC) exec backend python manage.py seed_demo

shell:          ## Django shell
	$(DC) exec backend python manage.py shell

psql:           ## Консоль PostgreSQL
	$(DC) exec postgres psql -U enduro -d enduro

check:          ## Проверки Django
	$(DC) exec backend python manage.py check

.PHONY: help up rates quotes down logs ps migrate makemigrations superuser seed shell psql check
