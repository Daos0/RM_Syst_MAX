## Структура

```text
frontend/
├── .env                                 # переменные окружения проекта
├── .gitignore                           # правила Git
├── astro.config.mjs                     # конфигурация Astro и SSR
├── eslint.config.mjs                   # настройки ESLint
├── package.json                         # зависимости и команды проекта
├── tsconfig.json                        # настройки TypeScript
├── public/
│   ├── browserconfig.xml                # настройки браузера и плиток
│   ├── favicon.ico                      # основной favicon
│   ├── favicons/                         # favicon и иконки PWA
│   ├── fonts/                            # IBM Plex Mono, Manrope, Space Grotesk
│   └── site.webmanifest                   # manifest сайта
├── src/
│   ├── admin/                              # заглушка будущей административной панели
│   ├── ai-widget/
│   │   ├── ChatErrorBoundary.tsx            # обработка ошибок чата
│   │   ├── ChatLauncher.tsx                 # кнопка открытия чата
│   │   ├── ChatWidget.tsx                   # основной виджет чата
│   │   ├── DeferredChatWidget.astro         # отложенная загрузка виджета
│   │   ├── UnifiedChat.tsx                  # единый интерфейс чата
│   │   ├── _CONNECT.md                      # подключение AI-виджета
│   │   ├── site.ts                          # настройки чата сайта
│   │   └── styles.css                       # стили AI-виджета
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AnalyticsNoscript.astro      # fallback аналитики
│   │   │   ├── AnalyticsTags.astro          # теги аналитики
│   │   │   ├── CitySwitcher.astro           # переключатель города
│   │   │   ├── Footer.astro                 # футер сайта
│   │   │   ├── Header.astro                 # шапка сайта
│   │   │   ├── PrivacyPolicyDialog.astro    # окно политики конфиденциальности
│   │   │   └── VerificationMeta.astro       # verification meta-теги
│   │   └── shared/
│   │       ├── LeadModal.astro              # модальное окно заявки
│   │       └── brand/
│   │           └── BrandLockup.astro        # фирменный блок RM Systems
│   ├── data/
│   │   ├── regions/index.ts                # данные регионов
│   │   ├── schema/index.ts                 # SEO Schema.org-данные
│   │   └── site/index.ts                   # общие тексты и навигация
│   ├── en/
│   │   ├── components/layout/EnCitySwitcher.astro # переключатель города EN
│   │   ├── data/locations/index.ts          # англоязычные локации
│   │   └── data/site.ts                    # англоязычные тексты сайта
│   ├── env.d.ts                             # типы окружения Astro
│   ├── layouts/
│   │   └── BaseLayout.astro                # базовый layout страниц
│   ├── middleware.ts                        # серверный middleware
│   ├── pages/
│   │   ├── [region]/
│   │   │   ├── about.astro                  # региональная страница о компании
│   │   │   ├── contacts.astro               # региональная страница контактов
│   │   │   ├── index.astro                  # региональная главная
│   │   │   └── services.astro               # региональные услуги
│   │   ├── about.astro                      # страница о компании
│   │   ├── contacts.astro                   # контакты
│   │   ├── en/
│   │   │   ├── about.astro                  # about на английском
│   │   │   ├── contacts.astro               # контакты на английском
│   │   │   ├── index.astro                  # английская главная
│   │   │   ├── locations/
│   │   │   │   ├── [city].astro             # страница города EN
│   │   │   │   ├── [city]/
│   │   │   │   │   ├── about.astro          # about города EN
│   │   │   │   │   ├── contacts.astro       # контакты города EN
│   │   │   │   │   └── services.astro       # услуги города EN
│   │   │   │   └── index.astro              # список городов EN
│   │   │   └── services.astro               # услуги на английском
│   │   ├── index.astro                      # главная страница
│   │   ├── privacy-policy.astro             # политика конфиденциальности
│   │   ├── robots.txt.ts                    # robots.txt
│   │   ├── services.astro                   # услуги
│   │   └── sitemap.xml.ts                   # sitemap.xml
│   ├── styles/
│   │   ├── global/
│   │   │   ├── base.css                     # базовые стили
│   │   │   ├── content.css                  # стили контента
│   │   │   ├── index.css                    # сборка глобальных стилей
│   │   │   ├── responsive.css               # адаптивные стили
│   │   │   └── tokens.css                   # дизайн-токены
│   │   └── shared/
│   │       ├── brand-lockup.css             # стили бренда
│   │       ├── city-switcher.css            # стили выбора города
│   │       ├── footer.css                   # стили футера
│   │       ├── forms.css                    # стили форм
│   │       ├── header.css                   # стили шапки
│   │       ├── index.css                    # сборка общих стилей
│   │       ├── lead-modal.css               # стили формы заявки
│   │       ├── mobile-menu.css              # мобильное меню
│   │       ├── navigation.css               # навигация
│   │       ├── privacy-modal.css             # модальное окно политики
│   │       └── typography.css               # типографика
│   └── utils/
│       └── site-routing.ts                  # маршрутизация сайта
└── tools/
    └── project-snapshot.py                  # снимок структуры проекта
```

Роман Михайлов ✦ RM Systems ✦ Создаю сайты, Mini Apps, чат-ботов и AI-решения для бизнеса. Интегрирую CRM, автоматизирую заявки, продажи и поддержку — от идеи до работающего цифрового продукта. ✦ https://rm-syst.ru/ ✦
