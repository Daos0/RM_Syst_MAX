# СТАРТ — MAX и Telegram (локально)

Проект: `/Users/sale/IT/RM_Systems/MAX`.

Здесь запускается только отдельный Compose-проект `max`: `web`, `max_bot`,
`telegram_bot` и общая PostgreSQL `db`. Команды не запускают, не
перезапускают и не останавливают
контейнеры основной RM-системы. Локальный healthcheck MAX:
`http://127.0.0.1:9810/health`.

Перед запуском должен работать Docker Desktop. Токены находятся в `.env`.
Каждый блок копируется целиком.

---

## Локальный запуск двух ботов и Mini App

Запускает PostgreSQL, MAX и Telegram, автоматически применяет миграции,
заполняет справочники, ждёт готовности и проверяет healthcheck.

```bash
cd "/Users/sale/IT/RM_Systems/MAX" && docker compose -p max config -q && docker compose -p max up -d --build --force-recreate --remove-orphans --wait --wait-timeout 120 web max_bot telegram_bot && docker compose -p max ps && curl -fsS --max-time 10 http://127.0.0.1:9810/health
```

Mini App после запуска открывается локально:

```text
http://127.0.0.1:9810/
```

---

## 1. Запуск с нуля всех сервисов покупок

Существующие данные PostgreSQL при обычном перезапуске сохраняются в volume.

```bash
cd "/Users/sale/IT/RM_Systems/MAX" && docker compose -p max down --remove-orphans && docker compose -p max config -q && docker compose -p max up -d --build --force-recreate --remove-orphans --wait --wait-timeout 120 web max_bot telegram_bot && docker compose -p max ps && curl -fsS --max-time 10 http://127.0.0.1:9810/health
```

---

## 2. Перезапуск после правок

```bash
cd "/Users/sale/IT/RM_Systems/MAX" && docker compose -p max config -q && docker compose -p max up -d --build --force-recreate --remove-orphans --wait --wait-timeout 120 web max_bot telegram_bot && docker compose -p max ps && curl -fsS --max-time 10 http://127.0.0.1:9810/health
```

---

## 3. Полная остановка

Контейнер остаётся на диске и может быть снова запущен.

```bash
cd "/Users/sale/IT/RM_Systems/MAX" && docker compose -p max stop -t 30 && docker compose -p max ps -a
```

---

## 4. Удалить контейнеры сервиса покупок

Удаляются только контейнеры и сеть Compose-проекта `max`. База в Docker volume
сохраняется, образы других проектов не затрагиваются.

```bash
cd "/Users/sale/IT/RM_Systems/MAX" && docker compose -p max down --remove-orphans && docker compose -p max ps -a
```

---

## 5. Снять логи

Команда показывает последние 200 строк и продолжает выводить новые. Выход:
`Ctrl+C` — бот при этом продолжит работать.

```bash
cd "/Users/sale/IT/RM_Systems/MAX" && docker compose -p max ps && docker compose -p max logs --tail=200 -f web max_bot telegram_bot db
```

---

## Проверить БД и backend тестами

Команда применяет миграции, повторно безопасно заполняет справочники и запускает
все тесты в отдельном контейнере.

```bash
cd "/Users/sale/IT/RM_Systems/MAX" && docker compose -p max --profile test build max_test && docker compose -p max --profile test run --rm max_test
```

---

## Production на VDS

Используется отдельный override: он подключает только HTTP-сервис `web` к сети
корневого Caddy. Остальные контейнеры `MAX` остаются изолированными.

Перед запуском production-профиль `.env.max.rm` должен содержать
`TELEGRAM_API_BASE_URL` собственного зарубежного релея, если Telegram API
недоступен напрямую с VDS.

```bash
cd /root/RM_Systems/MAX && docker compose -f compose.yaml -f compose.prod.yaml -p max config -q && docker compose -f compose.yaml -f compose.prod.yaml -p max up -d --build --remove-orphans --wait --wait-timeout 180 db web max_bot telegram_bot broadcast_worker && docker compose -f compose.yaml -f compose.prod.yaml -p max ps && curl -fsS --max-time 10 http://127.0.0.1:9810/health
```
