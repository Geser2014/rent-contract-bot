# Rent Contract Bot

Telegram-бот для автоматизации создания договоров аренды квартир. Распознаёт паспорт арендатора через Claude Vision AI, заполняет шаблон договора и отправляет готовый PDF — за 2-3 минуты вместо 25-40 минут ручной работы.

## Возможности

- **Диалоговый сбор данных** — пошаговый интерфейс с кнопками: выбор группы, квартиры, дат (календарь), сумм, контактов
- **OCR паспорта** — загрузка 2 страниц паспорта → распознавание через Claude Vision API → редактирование результатов
- **Сожители** — сканирование паспортов совместно проживающих (до 5 человек)
- **Генерация PDF** — заполнение TXT-шаблона + конвертация в PDF через LibreOffice
- **Суммы прописью** — автоматическая генерация на русском языке
- **История договоров** — `/history` с фильтром по году и месяцу, открытие PDF из чата
- **Статистика** — `/stats` с разбивкой по группам и месяцам
- **Хранение в БД** — все договоры сохраняются в SQLite

## Архитектура

```
Telegram Bot (FSM Dialog)
        │
   Services Layer
        │
   ┌────┼────┬──────────┐
   OCR  │ Document  │ Database
Service │ Service   │ (SQLite)
(Claude)│ (LibreOffice)
```

### Модули

| Модуль | Назначение |
|--------|------------|
| `main.py` | Точка входа, конфигурация Application + PicklePersistence |
| `config.py` | Загрузка .env, валидация, пути |
| `models.py` | ContractData (DTO) + Contract (SQLAlchemy ORM) |
| `database.py` | Async SQLAlchemy 2.0 + aiosqlite |
| `document_service.py` | Заполнение шаблонов, конвертация PDF, суммы прописью |
| `ocr_service.py` | Claude Vision API, распознавание паспортов |
| `validators.py` | Валидация дат, email, сумм, возраста |
| `logger.py` | Двойной вывод: консоль + ротируемый файл |
| `bot/handlers/conversation.py` | FSM-диалог создания договора (24 состояния) |
| `bot/handlers/history.py` | Команда /history — год → месяц → договоры → PDF |
| `bot/handlers/stats.py` | Команда /stats — статистика договоров |
| `apartments.json` | Фиксированные данные квартир (адрес, площадь, опись) |

## Установка и запуск

### Вариант 1: Docker (рекомендуется для VPS)

**Требования:** Docker + Docker Compose

```bash
# 1. Клонировать проект
git clone <repo-url>
cd rent-contract-bot

# 2. Создать .env файл
cp .env.example .env
nano .env
# Вставить:
#   TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
#   ANTHROPIC_API_KEY=ваш_ключ_от_console.anthropic.com

# 3. Положить шаблоны договоров
# Шаблоны уже в storage/templates/Подольская 38/ и Подольская 39/

# 4. Заполнить данные квартир
nano apartments.json
# Указать адреса, площади, описи имущества для каждой квартиры

# 5. Запуск
docker-compose up -d

# Логи
docker-compose logs -f

# Остановка
docker-compose down
```

### Вариант 2: Ручная установка

**Требования:**
- Python 3.10+
- LibreOffice (для конвертации PDF)

#### Linux (Ubuntu 22.04+)

```bash
# 1. Установить LibreOffice + шрифты
sudo apt update
sudo apt install -y libreoffice-core libreoffice-writer \
    fonts-crosextra-carlito fonts-crosextra-caladea

# 2. Клонировать и настроить
git clone <repo-url>
cd rent-contract-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Настроить .env
cp .env.example .env
nano .env

# 4. Заполнить apartments.json
nano apartments.json

# 5. Проверить LibreOffice
python scripts/verify_libreoffice.py

# 6. Запуск
python main.py
```

#### Windows

```bash
# 1. Установить LibreOffice: https://www.libreoffice.org/download/
# 2. Установить Python 3.10+: https://python.org

# 3. Настроить проект
git clone <repo-url>
cd rent-contract-bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 4. Настроить .env
copy .env.example .env
# Отредактировать .env — вставить токены

# 5. Запуск
python main.py
```

### Запуск как сервис на VPS (systemd)

```bash
# Создать файл сервиса
sudo nano /etc/systemd/system/rent-bot.service
```

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

```bash
# Активировать и запустить
sudo systemctl daemon-reload
sudo systemctl enable rent-bot
sudo systemctl start rent-bot

# Статус и логи
sudo systemctl status rent-bot
sudo journalctl -u rent-bot -f
```

## Получение токенов

### Telegram Bot Token

1. Откройте Telegram, найдите **@BotFather**
2. Отправьте `/newbot`
3. Введите имя бота (например, "Договоры аренды")
4. Введите username (например, `rent_contract_bot`)
5. Скопируйте токен в `.env` → `TELEGRAM_BOT_TOKEN`

### Anthropic API Key

1. Зайдите на [console.anthropic.com](https://console.anthropic.com)
2. Создайте аккаунт / войдите
3. Settings → API Keys → Create Key
4. Скопируйте ключ в `.env` → `ANTHROPIC_API_KEY`
5. Пополните баланс (минимум $5, одно распознавание ≈ $0.01)

## Использование бота

### Создание договора (`/start`)

1. **Выбор группы** — Подольская 39 или Подольская 38
2. **Выбор квартиры** — из списка кнопок
3. **Дата договора** — выбор через инлайн-календарь
4. **Дата Акта** — выбор через инлайн-календарь
5. **Срок договора** — в днях (например, 365)
6. **Сумма аренды** — ежемесячная (например, 50000)
7. **Депозит** — сумма + способ внесения (единовременно / 50%+50%)
8. **Телефон** — в любом формате
9. **Email** — электронная почта арендатора
10. **Telegram** — username арендатора
11. **Проживающие** — "1 человек" или "Совместное" (с OCR паспортов)
12. **Доп. условия** — "Нет" или ввести текст
13. **Паспорт арендатора** — 2 фото как файлы (не как фотографии!)
14. **Проверка OCR** — подтвердить / исправить / переснять
15. **Генерация** — PDF создаётся и отправляется в чат

### История договоров (`/history`)

Год → Месяц → Список договоров → Нажмите на договор чтобы получить PDF

### Статистика (`/stats`)

Общее количество, разбивка по группам квартир и по месяцам текущего года.

### Отмена (`/cancel`)

Отменяет создание договора на любом этапе.

## Настройка шаблонов

### Формат шаблонов

Шаблоны — TXT-файлы с плейсхолдерами в квадратных скобках:

```
ДОГОВОР № [НОМЕР_ДОГОВОРА]

г. Санкт-Петербург                    «[ДАТА_ДОГОВОРА]» г.

Гражданин РФ [ФИО_АРЕНДАТОРА], [ПОЛ], [ДАТА_РОЖДЕНИЯ] года рождения,
паспорт [СЕРИЯ_ПАСПОРТА] [НОМЕР_ПАСПОРТА], выдан [КЕМ_ВЫДАН]...
```

### Доступные плейсхолдеры

| Плейсхолдер | Источник | Описание |
|-------------|----------|----------|
| `[НОМЕР_ДОГОВОРА]` | Авто | П38/4/220209 |
| `[ДАТА_ДОГОВОРА]` | Диалог | 22.02.2026 |
| `[ДАТА_АКТА]` | Диалог | 22.02.2026 |
| `[ФИО_АРЕНДАТОРА]` | OCR | Полное ФИО |
| `[ПОЛ]` | OCR | М или Ж |
| `[ДАТА_РОЖДЕНИЯ]` | OCR | 11 марта 1986 |
| `[МЕСТО_РОЖДЕНИЯ]` | OCR | г. Ленинград |
| `[СЕРИЯ_ПАСПОРТА]` | OCR | 4025 |
| `[НОМЕР_ПАСПОРТА]` | OCR | 102574 |
| `[ДАТА_ВЫДАЧИ]` | OCR | 19 апреля 2025 |
| `[КЕМ_ВЫДАН]` | OCR | ГУ МВД по СПб... |
| `[КОД_ПОДРАЗДЕЛЕНИЯ]` | OCR | 780-001 |
| `[АДРЕС_РЕГИСТРАЦИИ]` | OCR | Полный адрес |
| `[ТЕЛЕФОН]` | Диалог | +79119269045 |
| `[EMAIL]` | Диалог | email@example.com |
| `[ТЕЛЕГРАМ]` | Диалог | @username |
| `[СУММА_АРЕНДЫ]` | Диалог | 50000 |
| `[СУММА_АРЕНДЫ_ПРОПИСЬЮ]` | Авто | пятьдесят тысяч |
| `[ДЕПОЗИТ]` | Диалог | 50000 |
| `[ДЕПОЗИТ_ПРОПИСЬЮ]` | Авто | пятьдесят тысяч |
| `[УСЛОВИЕ_ДЕПОЗИТ_НА_2_ЧАСТИ]` | Авто | Текст условия или пусто |
| `[ДЕНЬ_ОПЛАТЫ_ЦИФРА]` | Авто | 22 |
| `[ДЕНЬ_ОПЛАТЫ_ПРОПИСЬЮ]` | Авто | двадцать второго |
| `[АДРЕС_КВАРТИРЫ]` | apartments.json | Из данных квартиры |
| `[КОЛИЧЕСТВО_КОМНАТ]` | apartments.json | Из данных квартиры |
| `[ПЛОЩАДЬ]` | apartments.json | Из данных квартиры |
| `[ОПИСЬ_ИМУЩЕСТВА]` | apartments.json | Из данных квартиры |
| `[СПИСОК_ПРОЖИВАЮЩИХ]` | Диалог/OCR | ФИО + паспорт сожителей |
| `[СРОК_ДОГОВОРА]` | Диалог | В днях |
| `[ДОП_УСЛОВИЯ]` | Диалог | Текст или "Нет" |

### Расположение шаблонов

```
storage/templates/
├── Подольская 38/
│   ├── Моя.txt        ← квартира "Моя"
│   ├── Синяя.txt      ← квартира "Синяя"
│   ├── Зеленая.txt
│   ├── Эркер.txt
│   ├── Оранжевая.txt
│   ├── Красная.txt
│   ├── Винишко.txt
│   └── Двор.txt
└── Подольская 39/
    ├── 1.txt          ← квартира 1
    ├── 2.txt
    ├── 3.txt
    ├── 4.txt
    ├── 5.txt
    ├── 6.txt
    └── 7.txt
```

### Настройка apartments.json

Каждая квартира имеет фиксированные данные:

```json
{
  "Подольская 38": {
    "_short": "П38",
    "Моя": {
      "contract_num": "1",
      "address": "г. Санкт-Петербург, ул. Подольская, д. 38, кв. 1",
      "rooms": "1",
      "area": "25",
      "inventory": "Кровать, шкаф, стол, стулья 2 шт, холодильник..."
    }
  }
}
```

- `_short` — короткий код группы для номера договора (П38, П39)
- `contract_num` — номер квартиры в номере договора
- `address` — полный адрес для шаблона
- `rooms` — количество комнат
- `area` — площадь в м²
- `inventory` — опись имущества

## Формат номера договора

```
П38/4/220209
 │   │  │
 │   │  └── Дата: 22.02.2009 → 220209 (ДДММГГ)
 │   └───── Квартира: Эркер → 4 (из contract_num)
 └───────── Группа: Подольская 38 → П38 (из _short)
```

## Стоимость работы

| Компонент | Стоимость |
|-----------|-----------|
| Telegram Bot API | Бесплатно |
| LibreOffice | Бесплатно |
| Claude Vision OCR | ~$0.01 за договор (~1 руб) |
| **VPS (опционально)** | **от $5/мес** |

100 договоров ≈ $1. Основные расходы — VPS.

## Структура файлов проекта

```
rent-contract-bot/
├── main.py                          # Точка входа
├── config.py                        # Конфигурация
├── models.py                        # Модели данных
├── database.py                      # Работа с БД
├── document_service.py              # Генерация документов
├── ocr_service.py                   # Распознавание паспортов
├── validators.py                    # Валидация ввода
├── logger.py                        # Логирование
├── apartments.json                  # Данные квартир
├── requirements.txt                 # Зависимости
├── .env.example                     # Пример конфигурации
├── Dockerfile                       # Docker-образ
├── docker-compose.yml               # Docker Compose
├── bot/
│   └── handlers/
│       ├── conversation.py          # FSM-диалог (24 состояния)
│       ├── history.py               # /history
│       └── stats.py                 # /stats
├── scripts/
│   ├── create_templates.py          # Генерация DOCX-шаблонов
│   └── verify_libreoffice.py        # Проверка LibreOffice
├── storage/
│   ├── templates/                   # Шаблоны договоров (.txt)
│   ├── contracts/                   # Сгенерированные PDF
│   ├── logs/                        # Логи бота
│   ├── contracts.db                 # SQLite база данных
│   └── conversation_state.pkl       # Состояние диалогов
└── tests/                           # Тесты
```

## Решение проблем

### Бот не отвечает
- Проверьте `.env` — токены заполнены?
- `docker-compose logs` или `cat storage/logs/bot.log`

### PDF не создаётся
- LibreOffice установлен? `libreoffice --version` или `soffice --version`
- На Linux: `python scripts/verify_libreoffice.py`
- Шрифты установлены? `apt install fonts-crosextra-carlito fonts-crosextra-caladea`

### OCR плохо распознаёт
- Отправляйте паспорт как **файл** (📎 → Файл), не как фотографию
- Фото должно быть чётким, без бликов
- После распознавания нажмите "Нет, исправить" и поправьте нужные поля

### Ошибка "Договор с таким номером уже существует"
- Нельзя создать два договора с одинаковым номером (группа + квартира + дата)
- Создайте договор с другой датой или начните заново

## Лицензия

Проект для личного использования.
