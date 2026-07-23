## Структура

```text
deploy/
├── Caddyfile                         # reverse proxy и HTTPS
├── docker-compose.mac.yml             # локальный запуск на Mac
├── docker-compose.prod.yml            # production-запуск
├── docker-compose.vds.shared-host.yml # запуск на общем VDS
├── docker-compose.vpn.telegram.yml   # запуск Telegram через VPN
├── docker/
│   ├── ai_gateway.Dockerfile          # контейнер AI Gateway
│   ├── astro_site.Dockerfile          # контейнер Astro-сайта
│   ├── bitrix_bridge.Dockerfile       # контейнер интеграции Bitrix24
│   ├── broadcast_worker.Dockerfile    # фоновые рассылки
│   ├── client_bot.Dockerfile          # клиентский Telegram-бот
│   ├── leads_service.Dockerfile       # сервис обработки лидов
│   ├── owner_bot.Dockerfile            # административный Telegram-бот
│   ├── rag_service.Dockerfile         # сервис базы знаний и RAG
│   ├── srb_api.Dockerfile             # основной API
│   ├── srb_chat_api.Dockerfile        # API чата
│   └── srb_site.Dockerfile            # сервер сайта
├── env/
│   └── prod.env.example               # пример переменных production
├── requirements/
│   ├── ai_gateway.txt                 # зависимости AI Gateway
│   ├── bitrix_bridge.txt              # зависимости Bitrix24-моста
│   ├── bot_base.txt                   # общие зависимости ботов
│   ├── client_bot.txt                 # зависимости клиентского бота
│   ├── leads_service.txt              # зависимости сервиса лидов
│   ├── owner_bot.txt                  # зависимости админ-бота
│   ├── rag_service.txt                # зависимости RAG-сервиса
│   ├── srb_api.txt                    # зависимости основного API
│   ├── srb_chat_api.txt               # зависимости API чата
│   └── srb_site.txt                   # зависимости сервера сайта
└── vpn/
    └── xray-client.json               # конфигурация VPN-клиента
```

Роман Михайлов ✦ RM Systems ✦ Создаю сайты, Mini Apps, чат-ботов и AI-решения для бизнеса. Интегрирую CRM, автоматизирую заявки, продажи и поддержку — от идеи до работающего цифрового продукта. ✦ https://rm-syst.ru/ ✦
