# Roadmap: Rent Contract Bot

## Overview

Six phases that build in strict dependency order: scaffold and config first, then pure-code validation and DB schema, then document generation (testable without Telegram), then OCR service, then the FSM dialog layer that wires all services together, and finally integration with production-grade error handling. Core value — full contract cycle in 2-3 minutes — is delivered when Phase 6 completes.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Infrastructure** - Project scaffold, dependencies, environment config, LibreOffice verified
- [ ] **Phase 2: Validation and Data Layer** - Pydantic validators, SQLAlchemy models, ContractData dataclass
- [ ] **Phase 3: Document Generation** - DOCX template fill, LibreOffice PDF conversion, file management
- [ ] **Phase 4: OCR Service** - Claude Vision passport extraction, UNCLEAR handling, field validation
- [ ] **Phase 5: FSM Dialog Layer** - ConversationHandler, all states, inline keyboards, /cancel
- [ ] **Phase 6: Integration and Error Handling** - main.py wiring, error boundaries, logging, end-to-end test

## Phase Details

### Phase 1: Infrastructure
**Goal**: The project runs cleanly with all dependencies installed, environment configured, and critical infrastructure verified before any feature code is written
**Depends on**: Nothing (first phase)
**Requirements**: INFR-01, INFR-04
**Success Criteria** (what must be TRUE):
  1. `python main.py` starts without import errors or missing dependency errors
  2. `.env` file is loaded and bot token is validated at startup (bot connects to Telegram API)
  3. `storage/templates/` directory structure exists with correct group subdirectories
  4. LibreOffice headless converts a test DOCX to PDF without font substitution warnings
  5. Structured logger is configured and writes to console and log file
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — Project scaffold: pinned dependencies, .env.example, storage directory tree, main.py skeleton
- [ ] 01-02-PLAN.md — Config module, structured logging, LibreOffice verification script

### Phase 2: Validation and Data Layer
**Goal**: All data shapes and validation rules are codified in pure Python before any external service is called, giving every downstream layer a stable contract to program against
**Depends on**: Phase 1
**Requirements**: VALD-01, VALD-02, VALD-03, VALD-04, VALD-05, VALD-06, DB-01, DB-02
**Success Criteria** (what must be TRUE):
  1. Each validator (date, phone, email, amount, age) rejects invalid input and returns a user-readable error message
  2. Each validator accepts valid input and returns a normalized value
  3. The `Contract` SQLAlchemy model creates the SQLite table on `db.init()` with all required fields
  4. A `ContractData` dataclass instance can be constructed from fixture data and saved to the database without errors
**Plans**: TBD

### Phase 3: Document Generation
**Goal**: Given a populated `ContractData` object, the system produces a correctly formatted PDF contract file without any Telegram interaction
**Depends on**: Phase 2
**Requirements**: DOC-01, DOC-02, DOC-03
**Success Criteria** (what must be TRUE):
  1. Contract number is generated in `группа/квартира/дата` format and is unique per run
  2. A DOCX template for any apartment is filled with fixture data and all `{{ }}` placeholders are replaced
  3. The filled DOCX converts to a PDF that visually matches the template layout (fonts correct, no substitution artifacts)
  4. Temporary DOCX files are cleaned up after PDF conversion regardless of success or failure
**Plans**: TBD

### Phase 4: OCR Service
**Goal**: Given two passport image files, the service returns a structured dict of all required passport fields, or flags specific fields as UNCLEAR for human correction
**Depends on**: Phase 2
**Requirements**: OCR-01, OCR-02, OCR-03, OCR-04, OCR-05
**Success Criteria** (what must be TRUE):
  1. The OCR service accepts two image inputs (file paths or bytes) and calls Claude Vision API asynchronously
  2. A clear passport photo returns a populated dict with all 10 required fields (ФИО, дата рождения, место рождения, серия, номер, дата выдачи, кем выдан, код подразделения, адрес регистрации, пол)
  3. A low-quality or ambiguous field is returned as `UNCLEAR` rather than a guessed value
  4. The extracted data is displayed to the user in a readable summary for confirmation
  5. The user can confirm the data or reject it to restart the passport upload step
**Plans**: TBD
**UI hint**: yes

### Phase 5: FSM Dialog Layer
**Goal**: A user can navigate the complete contract creation dialog from group selection through confirmation, with all inputs validated inline and the ability to cancel at any point
**Depends on**: Phase 4
**Requirements**: DIAL-01, DIAL-02, DIAL-03, DIAL-04, DIAL-05, DIAL-06, DIAL-07, DIAL-08, DIAL-09, INFR-02, INFR-03
**Success Criteria** (what must be TRUE):
  1. Sending `/start` presents a group selection inline keyboard (Г39, Г38)
  2. After group selection, the bot shows available apartments for that group via inline keyboard
  3. The bot walks through all remaining inputs sequentially (dates, amounts, deposit method, phone, email) and validates each before advancing
  4. Sending `/cancel` at any state stops the dialog, clears session data, and sends a confirmation message
  5. Sending an unexpected input type (e.g., a sticker when a date is expected) triggers a helpful re-prompt instead of crashing
**Plans**: TBD
**UI hint**: yes

### Phase 6: Integration and Error Handling
**Goal**: All layers are wired together in `main.py` and the complete contract cycle runs end-to-end: group selection through PDF delivered in Telegram, with all external failures handled gracefully
**Depends on**: Phase 5
**Requirements**: DOC-04, INFR-05
**Success Criteria** (what must be TRUE):
  1. Completing the full dialog (group → apartment → dates → amounts → contacts → passport → confirm) delivers a PDF contract as a Telegram document in the same chat
  2. A Claude Vision API failure surfaces as a user-readable message ("Не удалось распознать паспорт, попробуйте снова") without a stack trace
  3. A LibreOffice conversion failure surfaces as a user-readable message and does not leave orphan temp files
  4. The bot continues operating normally after a handled error (no crash, no stuck state)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure | 0/2 | Not started | - |
| 2. Validation and Data Layer | 0/? | Not started | - |
| 3. Document Generation | 0/? | Not started | - |
| 4. OCR Service | 0/? | Not started | - |
| 5. FSM Dialog Layer | 0/? | Not started | - |
| 6. Integration and Error Handling | 0/? | Not started | - |
