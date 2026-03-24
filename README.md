# Rent Contract Bot

Telegram-бот для автоматизации создания договоров аренды квартир. Распознаёт паспорт арендатора через Claude Vision AI, заполняет шаблон договора и отправляет готовый PDF/DOCX — за 2-3 минуты вместо 25-40 минут ручной работы.

**Текущая версия:** v1.3-multi-group
**Кодовая база:** ~2300 строк Python, 11 модулей
**Тесты:** 76 (включая моки OCR, DB, интеграционные)

---

## Быстрый старт для разработчика

> При возвращении к проекту в новой сессии Claude Code скажите:
> **"Прочитай README.md и продолжаем работу над ботом аренды"**

### Ключевые файлы (читать в первую очередь)

| Файл | Строк | Что внутри |
|------|-------|------------|
| `bot/handlers/conversation.py` | 1043 | **Главный файл** — FSM-диалог, 25 состояний, все хендлеры |
| `document_service.py` | 376 | Генерация документов: TXT/DOCX шаблоны → PDF, суммы прописью |
| `ocr_service.py` | 218 | Claude Vision API, распознавание паспортов, 10 полей |
| `database.py` | 171 | Async SQLAlchemy: save, get, stats, history |
| `models.py` | 105 | ContractData (dataclass DTO) + Contract (ORM) |
| `apartments.json` | — | Конфиг квартир: группы, адреса, площади, номера для договоров |
| `bot/handlers/history.py` | 159 | /history — год → месяц → договоры → PDF |
| `bot/handlers/stats.py` | 39 | /stats — статистика |
| `main.py` | 54 | Точка входа: Application + PicklePersistence |

---

## Возможности

- **4 группы объектов** — Подольская 38, Подольская 39, Черная Речка, Заозерная (расширяемо через apartments.json)
- **Инлайн-календарь** для выбора дат (telegram-bot-calendar)
- **OCR паспорта** — 2 страницы → Claude Vision API (tool_use) → 10 полей → редактирование кнопками
- **Сожители** — OCR паспортов до 5 совместно проживающих
- **Генерация документов** — заполнение TXT или DOCX шаблонов + конвертация PDF через LibreOffice
- **Выбор формата** — PDF / DOCX / Оба
- **Суммы прописью** — автогенерация на русском (до 999 999 999)
- **История** — `/history` → год → месяц → список договоров → открытие PDF
- **Статистика** — `/stats` с разбивкой по группам и месяцам
- **Хранение в БД** — SQLite через async SQLAlchemy
- **Персистентность** — PicklePersistence сохраняет диалоги между перезапусками

---

## Архитектура

```
┌─────────────────────────────────┐
│  Telegram Bot (python-telegram-bot 22.x)  │
│  main.py → ApplicationBuilder + Polling    │
└────────────────┬────────────────┘
                 │
    ┌────────────┼────────────────┐
    │            │                │
┌───┴───┐  ┌────┴────┐  ┌───────┴───────┐
│ FSM   │  │ history │  │    stats      │
│ 25    │  │ year →  │  │ total/group/  │
│ states│  │ month → │  │ month         │
│       │  │ PDF     │  │               │
└───┬───┘  └────┬────┘  └───────┬───────┘
    │           │               │
    ├───────────┼───────────────┤
    │      Services Layer       │
    ├───────────┬───────────────┤
    │           │               │
┌───┴───┐  ┌───┴────┐  ┌───────┴───┐
│  OCR  │  │Document│  │ Database  │
│Service│  │Service │  │ (SQLite)  │
│(Claude│  │(Libre  │  │ async     │
│Vision)│  │Office) │  │           │
└───────┘  └────────┘  └───────────┘
```

---

## FSM-диалог (25 состояний)

Полный флоу создания договора в `bot/handlers/conversation.py`:

```
/start
  → GROUP                  — кнопки групп (из apartments.json)
  → APARTMENT              — кнопки квартир
  → CONTRACT_DATE          — инлайн-календарь
  → ACT_DATE               — инлайн-календарь
  → CONTRACT_DURATION      — ввод дней (365)
  → MONTHLY_AMOUNT         — ввод суммы
  → DEPOSIT_AMOUNT         — ввод суммы
  → DEPOSIT_METHOD         — кнопки: Единовременно / 50%+50%
  → PHONE                  — ввод (любой формат)
  → EMAIL                  — ввод с валидацией
  → TELEGRAM               — ввод @username
  → RESIDENTS_CHOICE       — кнопки: 1 человек / Совместное
     ├→ ROOMMATE_PAGE1     — загрузка файла паспорта сожителя
     ├→ ROOMMATE_PAGE2     — загрузка файла прописки сожителя
     ├→ ROOMMATE_CONFIRM_OCR — Да/Нет/Исправить/Переснять
     ├→ ROOMMATE_EDIT_FIELD — ввод нового значения поля
     ├→ ROOMMATE_MORE      — Ещё один / Больше нет (макс 5)
  → EXTRA_CONDITIONS_CHOICE — кнопки: Нет / Ввести
     └→ EXTRA_CONDITIONS_INPUT — ввод текста
  → PASSPORT_PAGE1         — загрузка файла паспорта арендатора
  → PASSPORT_PAGE2         — загрузка файла прописки + OCR
  → CONFIRM_OCR            — Да/Нет/Исправить/Переснять
     └→ EDIT_FIELD          — выбор поля кнопкой → ввод значения
  → CHOOSE_FORMAT          — кнопки: PDF / DOCX / Оба
  → CONFIRM                — генерация + сохранение + отправка
```

### Важные детали FSM

- **Паспорт принимается только как файл** (Document.ALL), не как фото — при отправке фото показывает предупреждение
- **OCR через tool_use** — Claude Vision возвращает structured JSON, нечитаемые поля = "UNCLEAR"
- **Редактирование OCR** — при "Нет, исправить" показывает 10 кнопок-полей с текущими значениями, тыкнул → ввёл новое → вернулся к списку
- **Сожители** — полный OCR каждого (2 страницы паспорта), данные форматируются строкой: "ФИО, пол, г.р., паспорт ..., зарег. по адресу ..."
- **Формат выбирается после OCR** — PDF (через LibreOffice), DOCX/TXT (исходный заполненный файл), или оба
- **Passport bytes удаляются** из user_data после OCR (экономия PicklePersistence)

---

## Модули — подробное описание

### main.py (54 строки)
Точка входа. `load_dotenv()` → `configure_logging()` → `config.validate()` → `ApplicationBuilder` с `PicklePersistence` и `concurrent_updates=False` → регистрация handlers → `run_polling()`.

`_post_init()` инициализирует БД и команды меню бота (`/start`, `/history`, `/stats`, `/cancel`).

### config.py (40 строк)
Загружает `.env`: `BOT_TOKEN`, `ANTHROPIC_KEY`, `LOG_LEVEL`, `STORAGE_DIR`. Вычисляет пути: `TEMPLATES_DIR`, `CONTRACTS_DIR`, `LOGS_DIR`, `DB_PATH`, `PERSISTENCE_PATH`. `validate()` проверяет токены и наличие директорий.

### models.py (105 строк)
- **ContractData** — `@dataclass`, DTO между слоями. 19 полей: contract_number, group, apartment, tenant_* (ФИО, дата рождения, место, пол, адрес), passport_* (серия, номер, дата, кем, код), tenant_phone/email, contract_date, act_date, monthly_amount (Decimal), deposit_amount (Decimal), deposit_split (bool), pdf_path.
- **Contract** — SQLAlchemy ORM, зеркалит ContractData + id, created_at.

### validators.py (65 строк)
Чистые функции, возвращают **нормализованное значение** или **строку ошибки на русском**:
- `validate_date(str)` → `datetime.date | str` (формат ДД.ММ.ГГГГ, год ≥ 2020)
- `validate_phone(str)` → `str` (нормализует в +7XXXXXXXXXX)
- `validate_email(str)` → `str` (lowercase)
- `validate_amount(str)` → `Decimal | str` (положительное число)
- `validate_age(dob, contract_date)` → `True | str` (18+)

**Особенность:** phone и email возвращают str и при успехе и при ошибке. В conversation.py для них используется `re.fullmatch()` вместо `isinstance(result, str)`.

### ocr_service.py (218 строк)
- `_CLAUDE_MODEL = "claude-sonnet-4-6"`
- `PASSPORT_FIELDS` — 10 полей: tenant_full_name, tenant_dob, tenant_birthplace, tenant_gender, passport_series, passport_number, passport_issued_date, passport_issued_by, passport_division_code, tenant_address
- `_PASSPORT_TOOL` — tool_use schema для structured output
- `_resize_image_bytes(bytes, max_px=1600)` — Pillow resize через `asyncio.to_thread()`
- `extract_passport_fields(page1_bytes, page2_bytes)` → dict — async, `tool_choice={"type":"tool","name":"extract_passport_fields"}`, логирует input/output tokens
- `get_unclear_fields(fields)` → list — поля со значением "UNCLEAR"
- `format_ocr_summary(fields)` → str — Telegram Markdown с русскими лейблами

**Стоимость:** ~$0.01 за распознавание (~1635 input + ~319 output tokens)

### document_service.py (376 строк)
**Данные квартир:**
- `APARTMENTS_DATA` — загружается из `apartments.json` при импорте
- `get_apartment_names(group)` — список квартир (исключая `_short`)
- `get_apartment_fixed_data(group, apt)` — address, rooms, area, inventory

**Номер договора:**
- `generate_contract_number(group, apt, date)` → `"П38/4/220209"` — short_group из `_short`, apt из `contract_num`, дата ДДММГГ

**Суммы прописью:**
- `amount_to_words(int)` → русский текст (до 999 999 999)
- Поддерживает миллионы, тысячи, женский/мужской род

**Шаблоны:**
- `_fill_txt_template(path, replacements)` — читает TXT, заменяет `[PLACEHOLDER]`
- `_fill_docx_template(path, replacements, output)` — python-docx, замена в параграфах и таблицах
- Приоритет: .docx → .txt

**PDF конвертация:**
- `_find_libreoffice()` — Windows: ищет `soffice.exe` в Program Files; Linux: `shutil.which("libreoffice")`
- `_convert_to_pdf(src, out_dir)` — subprocess, timeout=60, headless

**Главная функция:**
- `generate_contract(data, extra)` → str (pdf_path) — находит шаблон, заполняет, конвертирует

**30 плейсхолдеров:**
`[НОМЕР_ДОГОВОРА]`, `[ДАТА_ДОГОВОРА]`, `[ДАТА_АКТА]`, `[ФИО_АРЕНДАТОРА]`, `[ПОЛ]`, `[ДАТА_РОЖДЕНИЯ]`, `[МЕСТО_РОЖДЕНИЯ]`, `[СЕРИЯ_ПАСПОРТА]`, `[НОМЕР_ПАСПОРТА]`, `[КЕМ_ВЫДАН]`, `[ДАТА_ВЫДАЧИ]`, `[КОД_ПОДРАЗДЕЛЕНИЯ]`, `[АДРЕС_РЕГИСТРАЦИИ]`, `[ТЕЛЕФОН]`, `[EMAIL]`, `[ТЕЛЕГРАМ]`, `[СУММА_АРЕНДЫ]`, `[СУММА_АРЕНДЫ_ПРОПИСЬЮ]`, `[ДЕПОЗИТ]`, `[ДЕПОЗИТ_ПРОПИСЬЮ]`, `[УСЛОВИЕ_ДЕПОЗИТ_НА_2_ЧАСТИ]`, `[ДЕНЬ_ОПЛАТЫ_ЦИФРА]`, `[ДЕНЬ_ОПЛАТЫ_ПРОПИСЬЮ]`, `[АДРЕС_КВАРТИРЫ]`, `[КОЛИЧЕСТВО_КОМНАТ]`, `[ПЛОЩАДЬ]`, `[ОПИСЬ_ИМУЩЕСТВА]`, `[СПИСОК_ПРОЖИВАЮЩИХ]`, `[СРОК_ДОГОВОРА]`, `[ДОП_УСЛОВИЯ]`

### database.py (171 строка)
Async SQLAlchemy 2.0 + aiosqlite. Функции:
- `init()` — create tables (idempotent)
- `save_contract(ContractData)` → int (row id)
- `get_contracts(offset, limit)` → (list, total)
- `get_contracts_by_month(year, month)` → list
- `get_available_years()` → list[int]
- `get_available_months(year)` → list[int]
- `get_stats()` → dict (total, by_group, by_month)
- `get_contract_by_id(id)` → Contract | None
- `_configure(url)` — для тестов (in-memory DB)

### logger.py (46 строк)
`configure_logging(log_level, log_dir)` — StreamHandler (stdout) + RotatingFileHandler (5MB, 3 backups → storage/logs/bot.log). `get_logger(name)` → Logger.

### bot/handlers/history.py (159 строк)
`/history` → год кнопками → месяц кнопками → список договоров кнопками → нажал = получил PDF. Навигация "Назад к годам" / "Назад к месяцам". Только годы/месяцы с договорами.

### bot/handlers/stats.py (39 строк)
`/stats` → всего договоров, по группам с процентами, по месяцам текущего года.

---

## apartments.json — структура

```json
{
  "Подольская 38": {
    "_short": "П38",                    // код для номера договора
    "Моя": {                            // имя квартиры = имя шаблона (.txt/.docx)
      "contract_num": "1",              // номер в номере договора
      "address": "г. СПб, ул. ...",     // → [АДРЕС_КВАРТИРЫ]
      "rooms": "1",                     // → [КОЛИЧЕСТВО_КОМНАТ]
      "area": "25",                     // → [ПЛОЩАДЬ]
      "inventory": "Кровать, шкаф..."   // → [ОПИСЬ_ИМУЩЕСТВА]
    },
    "Синяя": { ... },
    ...
  },
  "Подольская 39": { "_short": "П39", "1": { ... }, ... },
  "Черная Речка": { "_short": "ЧР" },  // пока без квартир
  "Заозерная": { "_short": "З" }        // пока без квартир
}
```

**Добавление новой группы:** добавить ключ в JSON + создать папку в `storage/templates/` + положить шаблоны. Кнопки в боте генерируются автоматически.

**Добавление квартиры:** добавить в JSON + создать `{имя}.txt` или `{имя}.docx` в папке шаблонов.

---

## Формат номера договора

```
П38/4/220209
 │   │  │
 │   │  └── Дата: 22.02.2009 → 220209 (ДДММГГ)
 │   └───── Квартира: Эркер → 4 (из contract_num)
 └───────── Группа: Подольская 38 → П38 (из _short)
```

### Соответствие квартир → номеров (Подольская 38)

| Квартира | contract_num |
|----------|-------------|
| Моя | 1 |
| Синяя | 2 |
| Зеленая | 3 |
| Эркер | 4 |
| Оранжевая | 5 |
| Красная | 6 |
| Винишко | 7 |
| Двор | 8 |

---

## Шаблоны

### Расположение

```
storage/templates/
├── Подольская 38/
│   ├── Моя.txt         ← имя = ключ в apartments.json
│   ├── Синяя.txt
│   ├── Зеленая.txt
│   ├── Эркер.txt
│   ├── Оранжевая.txt
│   ├── Красная.txt
│   ├── Винишко.txt
│   └── Двор.txt
├── Подольская 39/
│   ├── 1.txt ... 7.txt
├── Черная Речка/       ← пока пусто
└── Заозерная/          ← пока пусто
```

### Формат

TXT или DOCX с плейсхолдерами `[НАЗВАНИЕ]`. Приоритет: `.docx` → `.txt`.

DOCX: замена через python-docx (параграфы + таблицы).
TXT: простой str.replace.
Оба конвертируются в PDF через LibreOffice headless.

---

## Установка и запуск

### Docker (рекомендуется для VPS)

```bash
git clone <repo-url> && cd rent-contract-bot
cp .env.example .env && nano .env   # вставить токены
docker-compose up -d
docker-compose logs -f              # логи
```

### Ручная установка (Windows)

```bash
pip install -r requirements.txt
copy .env.example .env              # вставить токены
python main.py
```

### Ручная установка (Linux)

```bash
sudo apt install -y libreoffice-core libreoffice-writer fonts-crosextra-carlito fonts-crosextra-caladea
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
python scripts/verify_libreoffice.py  # проверка
python main.py
```

### systemd сервис

```ini
[Unit]
Description=Rent Contract Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/rent-contract-bot
EnvironmentFile=/home/ubuntu/rent-contract-bot/.env
ExecStart=/home/ubuntu/rent-contract-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Получение токенов

### Telegram: @BotFather → /newbot → скопировать токен → .env TELEGRAM_BOT_TOKEN
### Anthropic: console.anthropic.com → API Keys → Create → .env ANTHROPIC_API_KEY ($5 минимум, $0.01/договор)

---

## Версии (git tags)

```
v1.0-working       — базовая рабочая версия
v1.1-full-flow     — календарь, OCR редактирование, сожители, кнопки
v1.2-history-stats — /history (год→месяц→PDF), /stats, OCR сожителей
v1.3-multi-group   — 4 группы, PDF/DOCX выбор, до 5 сожителей
```

Откат: `git checkout v1.3-multi-group`
Список: `git tag -l -n1`

---

## Известные особенности и решения

### LibreOffice на Windows
Бот ищет `soffice.exe` в `C:/Program Files/LibreOffice/program/`. Если путь другой — обновить `_find_libreoffice()` в `document_service.py`.

### Паспорт как файл, не фото
Telegram сжимает фотографии до ~0.87 JPEG. Паспорт нужно отправлять через 📎 → Файл, иначе OCR будет неточным. Бот показывает предупреждение если отправили как фото.

### Валидация телефона отключена
Телефон принимается в любом формате (без валидации). Phone и email валидаторы возвращают str на оба случая — в conversation.py используется regex вместо isinstance.

### PicklePersistence
Состояние диалогов сохраняется в `storage/conversation_state.pkl`. При изменении FSM-состояний нужно удалять этот файл (`rm storage/conversation_state.pkl`).

### concurrent_updates=False
Обязательно — без этого ConversationHandler ломается при параллельных сообщениях.

---

## Стоимость

| Компонент | Цена |
|-----------|------|
| Telegram Bot API | Бесплатно |
| LibreOffice | Бесплатно |
| Claude Vision OCR | ~$0.01/договор |
| VPS (опционально) | от $5/мес |

---

## Структура файлов

```
rent-contract-bot/
├── main.py                          # Точка входа (54 строки)
├── config.py                        # Конфигурация (40)
├── models.py                        # Модели данных (105)
├── database.py                      # Async DB (171)
├── document_service.py              # Генерация документов (376)
├── ocr_service.py                   # Распознавание паспортов (218)
├── validators.py                    # Валидация ввода (65)
├── logger.py                        # Логирование (46)
├── apartments.json                  # Данные квартир
├── requirements.txt                 # Зависимости
├── .env.example                     # Шаблон конфигурации
├── Dockerfile                       # Docker-образ
├── docker-compose.yml               # Docker Compose
├── bot/
│   └── handlers/
│       ├── conversation.py          # FSM-диалог (1043 строки, 25 состояний)
│       ├── history.py               # /history (159)
│       └── stats.py                 # /stats (39)
├── scripts/
│   ├── create_templates.py          # Генерация DOCX-шаблонов (не используется)
│   └── verify_libreoffice.py        # Проверка LibreOffice
├── storage/
│   ├── templates/                   # Шаблоны договоров (.txt/.docx)
│   │   ├── Подольская 38/ (8 квартир)
│   │   ├── Подольская 39/ (7 квартир)
│   │   ├── Черная Речка/  (пусто)
│   │   └── Заозерная/     (пусто)
│   ├── contracts/                   # Сгенерированные PDF + TXT/DOCX
│   ├── logs/                        # Логи бота
│   ├── contracts.db                 # SQLite БД
│   └── conversation_state.pkl       # Состояние диалогов
└── tests/                           # 76 тестов
    ├── test_validators.py           # 26 тестов валидаторов
    ├── test_database.py             # 4 теста БД
    ├── test_models.py               # 5 тестов моделей
    ├── test_document_service.py     # 8 тестов документов
    ├── test_ocr_service.py          # 15 тестов OCR
    ├── test_conversation.py         # 13 тестов FSM
    ├── test_integration.py          # 6 интеграционных
    └── fixtures/
        └── contract_template_test.docx
```

## TODO (не реализовано)

- [ ] Заполнить apartments.json реальными данными (адреса, площади, описи)
- [ ] Добавить квартиры для Черная Речка и Заозерная
- [ ] Положить шаблоны для новых групп
- [ ] Протестировать на Linux с LibreOffice (PDF генерация)
- [ ] Деплой на VPS
- [ ] Конвертация TXT → DOCX (сейчас если шаблон .txt, выдаёт .txt при выборе "DOCX")
