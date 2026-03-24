# Rent Contract Bot

## What This Is

Telegram-бот для автоматизации создания договоров аренды квартир. Бот собирает данные через диалог, распознаёт паспорт арендатора через Claude Vision API, заполняет DOCX-шаблон и отправляет готовый PDF. Предназначен для арендодателя, управляющего двумя группами объектов (Г39 и Г38).

## Core Value

Полный цикл создания договора аренды за 2-3 минуты вместо 25-40 минут ручной работы — от выбора квартиры до отправки готового PDF.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Диалоговый сбор данных: выбор группы → квартира → даты → суммы → контакты
- [ ] Загрузка и OCR-распознавание паспорта (2 страницы) через Claude Vision API
- [ ] Автозаполнение DOCX-шаблона данными из диалога и OCR
- [ ] Конвертация DOCX → PDF через LibreOffice headless
- [ ] Отправка готового PDF договора в Telegram
- [ ] Валидация всех вводимых данных (даты, телефон, email, суммы, возраст)
- [ ] Сохранение договоров в SQLite базу данных
- [ ] Генерация номера договора по формату группа/квартира/дата
- [ ] Подтверждение данных перед генерацией договора
- [ ] Логирование критических операций

### Out of Scope

- Real-time чат / нотификации — не нужно для текущего use case
- OAuth / сложная авторизация — бот для личного использования
- Мобильное приложение — Telegram достаточно
- Мультиязычность — только русский язык
- Редактирование сгенерированных договоров — проще создать заново

## Context

- Арендодатель управляет двумя группами объектов: Г39 (7 квартир) и Г38 (8 квартир)
- Для каждой квартиры есть свой DOCX-шаблон договора в `storage/templates/{группа}/{номер}.docx`
- Шаблоны содержат плейсхолдеры вида `[НАЗВАНИЕ_ПОЛЯ]` для автозаполнения
- Паспортные данные распознаются из двух фото: основная страница + прописка
- Депозит может вноситься единовременно или двумя частями (50% + 50%)
- Целевая платформа деплоя — Linux Ubuntu 22.04+

## Constraints

- **Tech stack**: Python 3.10+, python-telegram-bot 20.x (async), Anthropic Claude API, python-docx, SQLAlchemy + SQLite
- **PDF conversion**: LibreOffice headless (должен быть установлен на сервере)
- **AI model**: Claude Sonnet для OCR (баланс скорости и качества)
- **File size**: Максимум 10 MB для загружаемых фото паспорта

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Claude Vision для OCR вместо Tesseract | Лучшее качество распознавания рукописного текста и сложных форматов паспортов | — Pending |
| SQLite вместо PostgreSQL | Достаточно для одного пользователя, простота деплоя | — Pending |
| LibreOffice headless для PDF | Сохраняет форматирование DOCX-шаблонов лучше, чем python-библиотеки | — Pending |
| FSM через ConversationHandler | Встроенный в python-telegram-bot, не требует дополнительных зависимостей | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-24 after Phase 1 (Infrastructure) completion*
