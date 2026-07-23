# Осталось до production

Проект покупок — самостоятельный сервис в `/Users/sale/IT/RM_Systems/MAX`.
Он хранит собственную PostgreSQL, пользователей, списки, ботов и рассылки.

Связь с корневым `/Users/sale/IT/RM_Systems` нужна только для удобства:

- сайт и RM Admin разворачиваются общим контуром `deploy/`;
- RM Admin управляет проектом через защищённый HTTP API;
- общий reverse proxy публикует `max.rm-syst.ru`;
- исходники `MAX` попадают на тот же ВДС вместе с корневым deploy.

Бизнес-боты из `/Users/sale/IT/RM_Systems/src/bots` не являются частью проекта
покупок. У них свои данные, токены и исполнители рассылок.

## 1. Настроить production env

В `/root/RM_Systems/MAX/.env`:

- `MAX_BOT_TOKEN`, `MAX_BOT_USERNAME`;
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`;
- `TELEGRAM_MINI_APP_URL=https://max.rm-syst.ru/`;
- надёжный пароль PostgreSQL;
- случайный `ADMIN_BRIDGE_TOKEN`.

В корневом `/root/RM_Systems/.env`:

- существующие `CONTENT_ADMIN_LOGIN`, `CONTENT_ADMIN_PASSWORD`/hash и
  `SITE_JWT_SECRET` для входа в общую админку;
- `BOT_ADMIN_SOURCES=shopping`;
- `BOT_ADMIN_SHOPPING_LABEL=Покупки`;
- `BOT_ADMIN_SHOPPING_URL=https://max.rm-syst.ru`;
- `BOT_ADMIN_SHOPPING_TOKEN`, равный `ADMIN_BRIDGE_TOKEN` проекта.

## 2. Запустить сервисы MAX

```bash
cd /root/RM_Systems/MAX
docker compose -f compose.yaml -f compose.prod.yaml up -d --build db web max_bot telegram_bot broadcast_worker
```

`broadcast_worker` запускается отдельно от polling-процессов и обслуживает только
рассылки проекта покупок для MAX и Telegram.

## 3. Подключить внешний HTTPS

- проверить, что production override подключил `MAX/web` к сети
  `rm_systems_web` с alias `max_web`;
- направить `max.rm-syst.ru` на `max_web:8080` в Caddy;
- проверить TLS и `GET /health`;
- зарегистрировать этот HTTPS-адрес как Mini App в MAX и Telegram;
- внутренний admin API не публиковать без обязательного `X-Admin-Token`.

## 4. Контрольный сценарий

1. Войти в Mini App через реальный MAX-аккаунт и Telegram-аккаунт.
2. Проверить, что в RM Admin появились ровно два пользователя по своим каналам.
3. Создать общий список, подключить второго участника и проверить realtime.
4. Выгрузить CSV пользователей.
5. Создать тестовую рассылку на узкий сегмент, проверить аудиторию и только затем
   подтвердить отправку.
6. Проверить счётчики кампании и отсутствие повторной отправки после рестарта
   `broadcast_worker`.

После этого production-контур считается готовым к закрытому тестированию.
