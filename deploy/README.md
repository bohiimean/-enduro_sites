# Развёртывание на VPS

Сайт установлен в `/opt/enduro-site` на `95.182.93.90`. Адрес:
`http://95.182.93.90/`, админка: `http://95.182.93.90/admin/`.
Compose-проект называется `enduro-site`; контейнеры, сеть, PostgreSQL и тома
сайта отделены от проектов ботов. Боты не перезапускаются при обновлении сайта.

Это размещение на одном VPS с ботом и HTTP без TLS выбраны пользователем
отдельным запросом. Они отличаются от исходной схемы раздельного размещения
сайта и бота. При переходе к постоянному боевому размещению нужно вернуться
к требованиям географии и HTTPS из AGENTS.md.

## Конфигурация

Секреты находятся только в `/opt/enduro-site/.env` (права 600).
Пароли сайта и БД сгенерированы отдельно от паролей VPS и ботов.
Для явного HTTP-режима с отключённым DEBUG выставлены:

```dotenv
DJANGO_DEBUG=0
DJANGO_HTTP_PROTOCOL=http
DJANGO_COOKIE_SECURE=0
DJANGO_ALLOWED_HOSTS=95.182.93.90,localhost,127.0.0.1,backend
DJANGO_CSRF_TRUSTED_ORIGINS=http://95.182.93.90
HTTP_PORT=80
```

На HTTPS нужно заменить origin и протокол, а `DJANGO_COOKIE_SECURE` выставить
в `1`. По умолчанию при DEBUG=0 защищённые cookie остаются включены.

Из конфигурации основного бота скопированы только настройки менеджера,
Alfabit и резервного провайдера TwelveData. Токены Telegram и ключи Google
не копировались. Сайт не читает и не меняет базу или таблицы бота.

Почта пока не подключена. Созданы администратор и обычный пользователь с
подтверждёнными адресами в домене `.test`. Их доступы хранятся отдельно,
в `/root/enduro-site-access.json` (600), и переданы владельцу. Регистрация
и восстановление пароля для новых клиентов требуют настройки SMTP.

## Запуск и обслуживание

Все команды ниже выполняются в `/opt/enduro-site`:

```bash
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=100 backend worker
docker compose -f docker-compose.production.yml build backend
docker compose -f docker-compose.production.yml build frontend
docker compose -f docker-compose.production.yml build rates
docker compose -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml exec -T backend python manage.py check
```

Собирать образы последовательно: на VPS 4 ГБ ОЗУ, часть памяти занимает бот.
Стек имеет ограничения памяти и ротацию журналов. Backend запускается через
Gunicorn, Nuxt — из production-сборки. При старте backend применяются миграции,
создаётся кеш и собирается статика. Worker запускается после готовности backend.
Docker настроен перезапускать контейнеры после сбоя и перезагрузки сервера.

Сервис курсов находится в отдельном контейнере и не публикует порт наружу.
Обновление котировок идёт фоном; публичный API читает PostgreSQL.
Первый прогрев Chromium может занять несколько минут и временно нагружать
VPS. Не перезапускайте его только из-за долгого первого запроса.

Перед пересборкой загрузите актуальные исходники: текущая установка перенесена
архивом, отдельного Git checkout в `/opt/enduro-site` нет. Не заменяйте `.env`
при обновлении. Доступы и данные находятся вне исходного архива.

Для новой пустой БД справочники без демо-товаров заполняются командой:

```bash
docker compose -f docker-compose.production.yml exec -T backend python manage.py seed_demo --no-products
```

Эта команда не предназначена для регулярного запуска: она восстанавливает
стандартные наценки. Реальные товары, заказы и пользователи из локальной
среды разработки не переносились; каталог ведётся в админке.

## Резервные копии

`deploy/backup.sh` сохраняет отдельно PostgreSQL, медиа и конфигурацию.
Все три потока шифруются до записи на диск. Ключ:
`/root/enduro-site-backup.key`; файлы: `/var/backups/enduro-site`.
Расписание находится в `/etc/cron.d/enduro-site-backup`.
Ключ нужно хранить отдельно от копий; без него восстановление невозможно.
Копии на том же VPS не защищают от потери всего сервера.

Пример расшифровки БД (путь копии подставить свой):

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass file:/root/enduro-site-backup.key -in /path/to/db.dump.enc \
  > /root/restored-db.dump
```

Восстановление в рабочую базу выполнять отдельно после проверки копии
и согласования остановки сайта. Не использовать `down -v`: это удалит тома.
