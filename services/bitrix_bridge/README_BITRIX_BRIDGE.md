## Структура

```text
bitrix_bridge/
├── __init__.py                 # пакет интеграции Bitrix24
├── app.py                      # FastAPI-приложение моста
├── business_hours.py           # графики работы и режимы AI
├── config.py                   # настройки Bitrix-моста
├── dedup.py                    # защита от повторных событий
├── event_binding_runtime.py    # привязка событий Bitrix24
├── human_lock.py               # блокировка ответа при участии менеджера
├── identity.py                 # нормализация ID чатов и диалогов
├── memory_keys.py              # ключи памяти и областей портала
├── message_utils.py            # обработка сообщений и истории
├── openline_policy.py          # настройки открытых линий Bitrix24
├── portal_scope.py             # идентификаторы порталов
├── types.py                    # модели входящих событий
├── channels/
│   ├── __init__.py             # классификаторы каналов
│   ├── bitrix.py               # события Bitrix24
│   ├── telegram.py             # события Telegram
│   └── whatsapp.py             # события WhatsApp
├── parsing/
│   ├── __init__.py             # слой разбора входящих данных
│   └── incoming.py             # нормализация вебхуков Bitrix24
├── routes/
│   ├── __init__.py             # регистрация маршрутов
│   ├── admin.py                # административные маршруты
│   └── oauth.py                # OAuth-маршруты Bitrix24
├── runtime/
│   ├── __init__.py             # runtime-оркестрация моста
│   ├── extractors.py           # извлечение ID и целей ответа
│   ├── filters.py              # фильтрация входящих событий
│   ├── jobs.py                 # идентификаторы фоновых задач
│   ├── log_utils.py            # безопасное логирование и маскирование
│   └── webhook.py              # обработка вебхуков Bitrix24
└── services/
    ├── __init__.py             # внешние адаптеры сервиса
    ├── ai_gateway.py           # клиент AI Gateway
    ├── bitrix_api.py           # клиент REST API Bitrix24
    └── dedup_store.py          # хранилище дедупликации
```

Роман Михайлов ✦ RM Systems ✦ Создаю сайты, Mini Apps, чат-ботов и AI-решения для бизнеса. Интегрирую CRM, автоматизирую заявки, продажи и поддержку — от идеи до работающего цифрового продукта. ✦ [rm-syst.ru](https://rm-syst.ru/) ✦
