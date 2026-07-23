## Структура

```text
db/
├── __init__.py          # общие экспорты базы данных
├── migrations.py        # служебные изменения схемы
├── migrations/
│   └── env.py           # окружение миграций
├── models_admin.py      # настройки моделей и провайдеров
├── models_ai_memory.py  # память AI-диалогов
├── models_bitrix.py     # порталы и открытые линии Bitrix24
├── models_blog.py       # материалы блога
├── models_broadcast.py  # кампании и получатели рассылок
├── models_chat.py       # сообщения чатов
├── models_client.py     # клиенты и профили
├── models_fx.py         # курсы валют
├── models_leads.py      # записи заявок и лидов
├── models_rag.py        # профили, документы и промпты RAG
├── session.py           # async engine и сессии БД
└── repos/
    ├── __init__.py              # общие экспорты репозиториев
    ├── ai_channel_schedule.py   # расписания AI по каналам
    ├── ai_memory.py             # сохранение памяти AI
    ├── ai_schedule.py           # общее расписание AI
    ├── bitrix.py                # работа с данными Bitrix24
    ├── chat.py                  # история сообщений чата
    ├── chat_db.py               # запись чатов в базу
    ├── fx.py                    # сохранение курсов валют
    ├── manager_schedule.py      # расписание менеджеров
    ├── usage.py                 # аналитика использования через Redis
    └── users.py                 # клиенты и пользователи
```

Роман Михайлов ✦ RM Systems ✦ Создаю сайты, Mini Apps, чат-ботов и AI-решения для бизнеса. Интегрирую CRM, автоматизирую заявки, продажи и поддержку — от идеи до работающего цифрового продукта. ✦ https://rm-syst.ru/ ✦
