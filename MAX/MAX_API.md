# MAX: карта проекта и подключений

Этот файл — главная точка входа для работы с коммерческим MAX-ботом.
Рабочая папка проекта:

```text
/Users/sale/IT/RM_Systems/MAX
```

MAX должен разрабатываться, запускаться и обслуживаться из этой папки.
Код и данные основной RM-системы не являются частью MAX. Единственная
разрешённая интеграция с RM — защищённый HTTP API сервиса `ai_gateway`.

> Текущее состояние: создано и локально запущено базовое приложение бота,
> мини-приложение и отдельный Compose с сервисом `max_bot`. База данных,
> Webhook и бизнес-логика пока не создавались.

## 1. Граница проекта

```text
MAX API ──HTTPS Webhook──> max_bot ──> max_db
                              │
                              └──HTTP + Bearer token──> ai_gateway
```

Правила границы:

- MAX имеет собственный `compose.yaml`, `.env`, PostgreSQL и Docker volume.
- Запуск или остановка MAX не должны перезапускать RM-систему.
- MAX не подключается напрямую к `srb_db`, `srb_redis`, `rag_service`,
  `qdrant`, `leads_service` или другим внутренним сервисам RM.
- Доступ к AI выполняется только через `ai_gateway`.
- Секреты хранятся только в `MAX/.env`; токены запрещено записывать в код,
  документацию и Git.
- Внешний доступ получает только Webhook MAX через HTTPS. БД наружу не
  публикуется.

## 2. Целевая структура папки MAX

```text
MAX/
├── MAX_API.md              # этот обзор и карта интеграций
├── app/                    # код бота и HTTP Webhook
├── migrations/             # миграции собственной БД
├── tests/                  # тесты MAX
├── compose.yaml            # отдельный Docker Compose-проект
├── Dockerfile
├── pyproject.toml
├── .env                    # реальные секреты, только локально/на сервере
├── .env.example            # имена переменных без секретных значений
└── README.md               # установка и эксплуатация
```

## 3. Сервисы MAX

| Сервис | Назначение | Сеть | Внешний порт |
|---|---|---|---|
| `max_bot` | Webhook MAX, бизнес-логика совместных покупок, вызов AI | `max_private`, `max_ai_bridge` | только через reverse proxy |
| `max_db` | Пользователи, покупки, группы, участники, статусы, аудит | только `max_private` | нет |

На старте Redis не добавляется. Состояние покупок должно храниться в
PostgreSQL. Redis добавляется только при появлении подтверждённой задачи для
очередей, блокировок или кэша.

Compose-проект всегда запускается с именем `max`:

```bash
cd /Users/sale/IT/RM_Systems/MAX
docker compose -p max up -d
docker compose -p max ps
docker compose -p max logs -f max_bot
docker compose -p max stop
```

Эти команды начнут работать после создания `compose.yaml`.

## 4. Подключение к платформе MAX

Production-схема:

```text
Платформа MAX
    -> https://max.rm-syst.ru
    -> существующий reverse proxy сервера
    -> max_bot:<внутренний-порт>
```

Зарезервированный публичный адрес мини-приложения:

```text
https://max.rm-syst.ru
```

В DNS создана запись `A`: `max.rm-syst.ru` → `77.223.97.164`. Она не меняет
маршрутизацию основного сайта `rm-syst.ru`: Caddy выбирает сервис по имени
хоста. Закомментированная заглушка будущего маршрута находится в корневом
`/Users/sale/IT/RM_Systems/deploy/Caddyfile`, блок `FUTURE MAX`. Она пока
выключена и не влияет на локальный запуск или основной сайт.

Настройки, которые позже должны появиться в `MAX/.env`:

```dotenv
MAX_BOT_TOKEN=
MAX_API_BASE_URL=https://platform-api2.max.ru
MAX_WEBHOOK_PUBLIC_URL=https://max.rm-syst.ru/<секретный-webhook-путь>
MAX_WEBHOOK_SECRET=
```

Токен MAX передаётся платформе в HTTP-заголовке `Authorization`, а не в URL.
Для production используется HTTPS Webhook с сертификатом доверенного центра.
Long Polling не используется в production.

Официальная документация:

- https://dev.max.ru/docs-api
- https://dev.max.ru/docs/chatbots/bots-coding/masterbot

## 5. Единственное подключение к RM: AI Gateway

Существующий сервис находится в основном проекте:

```text
Код: /Users/sale/IT/RM_Systems/services/ai_gateway
Docker-сервис: ai_gateway
Внутренний порт: 9100
```

Планируемый адрес из контейнера `max_bot`:

```dotenv
AI_GATEWAY_URL=http://ai_gateway:9100
AI_GATEWAY_TOKEN=
```

Контейнеры `max_bot` и `ai_gateway` должны быть единственными участниками
отдельной внешней Docker-сети `max_ai_bridge`. База `max_db` остаётся только
в закрытой сети `max_private`.

### Состояние безопасности AI-интеграции

Сейчас существующие маршруты `ai_gateway` не проверяют Bearer-токен. До
подключения коммерческого MAX-бота необходимо добавить сервисную авторизацию,
лимит запросов и отдельный учёт расходов для источника `max`.

До выполнения этого требования подключение MAX к `ai_gateway` считается
не готовым для production.

### Проверка доступности

```http
GET /health HTTP/1.1
Host: ai_gateway:9100
```

Ожидаемая форма ответа:

```json
{
  "status": "ok",
  "warming_up": false
}
```

### Обычный AI-запрос

```http
POST /chat HTTP/1.1
Host: ai_gateway:9100
Authorization: Bearer <AI_GATEWAY_TOKEN>
Content-Type: application/json
```

```json
{
  "user_id": "max:<внутренний-id-пользователя>",
  "question": "Текст запроса пользователя",
  "source": "max",
  "ext_user_id": "<id-пользователя-в-MAX>",
  "meta": {
    "purchase_id": "<id-совместной-покупки>"
  },
  "return_payload": false
}
```

Форма ответа:

```json
{
  "answer": "Ответ AI",
  "provider": "<провайдер>",
  "model": "<модель>",
  "token_counts": {
    "prompt": 0,
    "completion": 0,
    "total": 0
  },
  "payload": null
}
```

Для потокового ответа используется `POST /chat/stream` с тем же основным
телом запроса. Формат ответа — Server-Sent Events (`text/event-stream`).

## 6. Важные сервисы корня RM

Эта таблица нужна только для понимания окружения. Она не разрешает MAX
подключаться к перечисленным сервисам.

| Сервис RM | Внутренний порт | Назначение | Доступ из MAX |
|---|---:|---|---|
| `ai_gateway` | 9100 | Единый вход в AI-модуль | **да, через `max_ai_bridge` и токен** |
| `srb_db` | 5432 | Основная PostgreSQL RM | нет |
| `srb_redis` | 6379 | Очереди и кэш RM | нет |
| `rag_service` | 9200 | RAG основной системы | нет, только опосредованно через AI Gateway |
| `qdrant` | 6333 | Векторное хранилище RM | нет |
| `leads_service` | 9300 | Лиды RM | нет |
| `srb_api` | 8000 | API основной системы | нет |
| `srb_chat_api` | 9000 | Чат API основной системы | нет |
| `bitrix_bridge` | 9700 | Интеграция Bitrix | нет |

Основной Compose:

```text
/Users/sale/IT/RM_Systems/docker-compose.yml
```

Production-сети основной системы:

```text
/Users/sale/IT/RM_Systems/deploy/docker-compose.prod.yml
```

Менять эти файлы из задач MAX нельзя, кроме отдельной согласованной задачи по
добавлению `ai_gateway` в сеть `max_ai_bridge` и его сервисной авторизации.

## 7. Собственная база MAX

MAX использует отдельный контейнер PostgreSQL, отдельного пользователя,
отдельную базу и отдельный Docker volume. Пример имён переменных без значений:

```dotenv
MAX_DATABASE_URL=postgresql+asyncpg://max_app:<password>@max_db:5432/max_main
MAX_POSTGRES_DB=max_main
MAX_POSTGRES_USER=max_app
MAX_POSTGRES_PASSWORD=
```

Запрещено использовать `DATABASE_URL` основной RM-системы или давать роли
`max_app` доступ к `srb_db`.

Минимальные доменные сущности будущей БД:

- пользователь MAX;
- группа совместной покупки;
- магазин;
- покупка;
- участник покупки;
- позиция и количество;
- платежный/расчётный статус без хранения реквизитов карт;
- событие Webhook для идемпотентной обработки;
- журнал важных действий.

## 8. Обязательные эксплуатационные правила

1. Все команды MAX выполняются из `/Users/sale/IT/RM_Systems/MAX`.
2. У MAX собственный цикл запуска, миграций, тестов и резервного копирования.
3. Команды `raskat` и `proverka` относятся к клонам RM и для разработки MAX
   не используются.
4. MAX не импортирует Python-модули из родительских папок `shared/`,
   `services/`, `dao/` или `src/`. Интеграция только по HTTP-контракту.
5. В `.env.example` допускаются только пустые или безопасные примерные
   значения.
6. Webhook обрабатывается идемпотентно: повтор одного события не должен
   создавать вторую покупку, позицию или участника.
7. Логи не должны содержать токены, персональные данные, номера телефонов и
   полные тела чувствительных запросов.
8. Бэкап `max_db` проверяется отдельным тестовым восстановлением.

## 9. Ближайшая точка разработки

Следующий этап — создать внутри `MAX` автономный каркас: `compose.yaml`,
`Dockerfile`, приложение Webhook, миграции, `.env.example`, healthcheck и
тест соединения с заглушкой AI Gateway. Запущенные процессы RM при этом не
изменяются.
