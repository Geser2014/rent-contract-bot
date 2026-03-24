# Feature Research

**Domain:** Telegram bot for rental contract automation (personal landlord tool, Russian market)
**Researched:** 2026-03-24
**Confidence:** MEDIUM — no direct competitors exist at this exact scope; extrapolated from document automation bots, lease management software, and Telegram FSM bot patterns

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the landlord-user assumes exist. Missing any of these and the bot feels broken or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Guided dialog (step-by-step data collection) | Any form-filling bot must ask questions sequentially; dropping the user into a blank form is hostile | LOW | FSM via `ConversationHandler`; states: group → apartment → tenant info → dates → amounts → confirmation |
| Apartment/group selection via inline keyboard | The landlord has fixed inventory (Г39: 7 units, Г38: 8 units); free-text apartment entry would cause errors | LOW | `InlineKeyboardMarkup`; apartment list is static config |
| Passport OCR — both pages | Core value prop — eliminates manual re-typing of passport data; two pages needed (identity + registration) | MEDIUM | Claude Vision API; prompts must extract specific Russian passport fields |
| OCR result review before contract generation | OCR has non-zero error rate on poor photos; user must be able to see and correct extracted fields | MEDIUM | Display extracted fields as editable summary; let user correct individual fields or re-upload photo |
| Auto-filled DOCX template | The end artifact; without this, the bot is just a form | MEDIUM | `python-docx` placeholder replacement; one template per apartment |
| DOCX → PDF conversion | PDF is the expected deliverable format; DOCX is an implementation detail | LOW | LibreOffice headless; must be installed on deploy server |
| PDF delivered in Telegram | The user should receive the final file without leaving the app | LOW | `bot.send_document()` after generation |
| Data validation — all inputs | Dates, phone, amounts, age — bad data silently corrupts contracts | MEDIUM | Validate at each FSM state; re-prompt on failure with clear error message |
| Confirmation screen before generation | "Generate contract" is irreversible (practically); user must see a summary and confirm | LOW | Display all collected data; inline "Confirm / Edit" buttons |
| Contract number generation | Every contract needs a unique reference; format dictated by landlord's existing system | LOW | Format: `{group}/{apartment}/{date}` — deterministic, no database lookup needed for generation |
| /cancel command at any state | Users make mistakes mid-flow; bot must be escapable without restarting Telegram | LOW | `ConversationHandler` fallback; clears session state |
| Error handling with user-readable messages | API failures, LibreOffice failures, network timeouts must not show stack traces | LOW | Try/except at every external call; friendly fallback messages |

### Differentiators (Competitive Advantage)

Features beyond baseline that provide meaningful value for this specific use case. Given this is a personal tool (not a SaaS product), "competitive advantage" means: reduces landlord friction or prevents costly mistakes.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Split-deposit flow (50%+50%) | Landlord's specific business rule; generic tools don't handle this | LOW | Add deposit_type field to FSM; two amount fields if split; template must support both variants |
| Per-apartment DOCX templates | Each of 15 apartments may have unique terms (address, room count, price range); one-size template risks errors | LOW | Template lookup: `storage/templates/{group}/{unit}.docx`; already designed this way |
| Tenant age validation against passport birth date | Prevents accidentally creating contracts with minors; caught at OCR review step | LOW | Compare extracted birth date to 18-year threshold before proceeding |
| SQLite contract history | Landlord can look up past contracts without digging through Telegram history | MEDIUM | Store: contract number, tenant name, apartment, dates, amounts, generated_at; no PII beyond what's in the PDF |
| Structured logging of critical ops | When something goes wrong (OCR fails, PDF not sent), landlord needs a diagnostic trail | LOW | Log: photo receipt, OCR call, template fill, PDF conversion, document send — each with timestamp and outcome |
| /start restarts cleanly | Telegram users instinctively hit /start when lost; bot must handle this mid-conversation gracefully | LOW | Map /start as entry point AND as fallback that resets state |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem valuable but would add complexity without commensurate benefit for this use case.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| E-signature integration | "Professional" contracts should be e-signed | Requires third-party service (Kontur.Crypto, DocuSign), adds API dependency, costs money, complicates flow significantly; landlord's existing process likely handles signing in-person | Deliver PDF; landlord and tenant sign physically or in a separate tool |
| CRM / external system sync | Property management software expects data export | Out of scope for a personal tool; the landlord manages two buildings, not a portfolio company | SQLite history is sufficient; export to CSV later if needed |
| Multi-user / role-based access | "What if an assistant needs access?" | This is explicitly a personal tool; adding auth multiplies complexity; Telegram user ID check is sufficient access control | Hardcode authorized user ID(s) in config; expand only if needed |
| Template editor in-bot | "I want to modify contract terms without touching files" | In-bot file editing is fragile; template structure must remain valid DOCX; easier to edit the file directly | Edit DOCX files on the server; restart bot to pick up changes |
| Automatic tenant notification | "Send the contract to the tenant too" | Landlord controls who gets the document; tenant may not use Telegram; complicates flow with contact verification | Landlord downloads PDF and forwards it themselves |
| Real-time rent payment tracking | "Track whether tenant paid this month" | Completely different domain (accounting); would balloon scope; proper tools exist (spreadsheets, banking apps) | Out of scope entirely |
| Contract renewal / amendment | "Generate an amendment to extend the lease" | Different document type; different data collection flow; edge cases multiply; very low frequency | Create a new contract; amendment templates can be a v2 feature |
| OCR-only mode (without contract generation) | "I just want to read the passport" | Degrades the bot into a generic OCR tool; dilutes the focused value prop | Keep OCR tightly coupled to the contract generation flow |

---

## Feature Dependencies

```
[Apartment Selection]
    └──requires──> [Group Selection]

[OCR — Passport Recognition]
    └──requires──> [Photo upload accepted by Telegram]
    └──enhances──> [Data Collection Dialog] (pre-fills tenant fields)

[OCR Result Review / Correction]
    └──requires──> [OCR — Passport Recognition]
    └──blocks──> [Confirmation Screen] (must complete before proceeding)

[Confirmation Screen]
    └──requires──> [Data Collection Dialog complete]
    └──requires──> [OCR Result Review / Correction complete]

[DOCX Template Fill]
    └──requires──> [Confirmation Screen — user confirmed]
    └──requires──> [Per-apartment template exists on disk]

[PDF Conversion]
    └──requires──> [DOCX Template Fill]
    └──requires──> [LibreOffice headless installed]

[PDF Delivery via Telegram]
    └──requires──> [PDF Conversion]

[Contract Number Generation]
    └──requires──> [Group Selection]
    └──requires──> [Apartment Selection]
    └──requires──> [Dates collected]
    └──feeds──> [DOCX Template Fill]

[SQLite History Record]
    └──requires──> [PDF Delivery via Telegram succeeded]
    └──enhances──> [Contract Number Generation] (record stored with number)

[Split-Deposit Flow]
    └──enhances──> [Data Collection Dialog] (conditional branch)
    └──feeds──> [DOCX Template Fill] (two amount fields vs one)

[Tenant Age Validation]
    └──requires──> [OCR — Passport Recognition] (birth date extracted)
    └──blocks──> [Confirmation Screen] if age < 18
```

### Dependency Notes

- **OCR Result Review requires OCR first:** The review/correction step only makes sense after extraction; it cannot be skipped even when OCR confidence is high — this is the human-in-the-loop checkpoint that prevents bad data propagating into the contract.
- **PDF Conversion requires LibreOffice headless:** This is an infrastructure dependency, not a code dependency. Must be provisioned on the server before the bot can run. Failure mode: PDF step fails silently if LibreOffice is missing.
- **Split-Deposit Flow enhances Data Collection Dialog:** The deposit type question branches the FSM — single deposit skips the second amount state. Both paths must eventually produce values for the same template placeholders.
- **Contract Number Generation feeds DOCX Template Fill:** The number is generated deterministically from group/apartment/date, so it can be computed right before template fill without a database lookup.

---

## MVP Definition

### Launch With (v1)

Minimum set to achieve the core value: full contract cycle in 2-3 minutes.

- [ ] Group → apartment selection via inline keyboard — entry point, establishes context for everything
- [ ] Guided dialog: tenant name, phone, email, dates, rent amount, deposit type + amount(s) — collects all non-passport data
- [ ] Photo upload and OCR via Claude Vision (both passport pages) — core time-saving feature
- [ ] OCR result display with field-by-field correction — necessary for accuracy; no human review = unusable for legal docs
- [ ] Confirmation screen with all data — prevents costly mistakes
- [ ] DOCX template fill with placeholder replacement — produces the contract
- [ ] DOCX → PDF via LibreOffice headless — delivers expected format
- [ ] PDF sent to user in Telegram — closes the loop
- [ ] Input validation at each step (dates, phone, amounts, age) — prevents silent corruption
- [ ] /cancel at any state — basic UX hygiene
- [ ] Contract number generation (group/apartment/date format) — required for filing

### Add After Validation (v1.x)

Features to add once the core flow is working reliably.

- [ ] SQLite contract history — add when landlord asks "what were the terms for apartment 3 last month?"; add after v1 is used a few times
- [ ] Structured logging to file — add when first production failure occurs and debugging is needed
- [ ] Split-deposit flow — add when landlord encounters a tenant who wants to pay deposit in two parts

### Future Consideration (v2+)

Defer until v1 is proven.

- [ ] Contract amendment templates — low frequency, different document flow; defer until explicitly requested
- [ ] CSV/Excel export of contract history — only needed if landlord outgrows manual SQLite inspection
- [ ] Multiple authorized users — only if landlord hires an assistant

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Guided dialog (FSM) | HIGH | LOW | P1 |
| Apartment/group selection | HIGH | LOW | P1 |
| Passport OCR (Claude Vision) | HIGH | MEDIUM | P1 |
| OCR result review + correction | HIGH | MEDIUM | P1 |
| DOCX template fill | HIGH | MEDIUM | P1 |
| PDF conversion (LibreOffice) | HIGH | LOW | P1 |
| PDF delivery in Telegram | HIGH | LOW | P1 |
| Data validation | HIGH | MEDIUM | P1 |
| Confirmation screen | HIGH | LOW | P1 |
| Contract number generation | MEDIUM | LOW | P1 |
| /cancel command | MEDIUM | LOW | P1 |
| Error handling (user-readable) | HIGH | LOW | P1 |
| Split-deposit flow | MEDIUM | LOW | P2 |
| SQLite history | MEDIUM | MEDIUM | P2 |
| Structured logging | MEDIUM | LOW | P2 |
| Tenant age validation | LOW | LOW | P2 |
| Per-apartment templates | HIGH | LOW | P1 (already designed in) |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

No direct competitors exist at this exact scope (personal Telegram bot, Russian landlord, 15 apartments). The closest analogues are:

| Feature | Lease Management SaaS (e.g., Buildium) | Telegram Document Bots (e.g., Botman.one) | This Bot |
|---------|----------------------------------------|-------------------------------------------|----------|
| Contract generation | Template-based, web UI | PDF generation via platform | DOCX templates per apartment, CLI |
| OCR / passport extraction | Not standard; some use ID verification APIs | Mentioned as capability | Claude Vision API — higher quality for Russian passport handwriting |
| E-signature | Standard feature | Via Kontur.Crypto integration | Out of scope — physical signature |
| Multi-property | Yes, designed for portfolios | Yes | 2 groups, 15 units — fixed inventory |
| Tenant portal | Yes | No | No — landlord-only tool |
| Delivery channel | Email / web download | Telegram | Telegram |
| Setup complexity | High (onboarding, pricing, training) | Medium (platform integration) | Low (self-hosted, personal config) |
| Russian passport field extraction | Unlikely (international products) | Possible via FMS API | First-class — Russian passport structure hardcoded into OCR prompt |

**Key insight:** The differentiation is not in the feature list — it is in the combination of Claude Vision quality for Russian-language documents, zero external service dependencies beyond the Claude API, and the sub-5-minute total flow optimized for a single landlord's exact inventory.

---

## Sources

- [Telegram Bots for Business: Document Automation Cases (Botman.one)](https://botman.one/en/blog/post?post_id=82) — real-world rental contract bot feature set, MEDIUM confidence
- [Best AI Lease Abstraction Tools 2026 (Baselane)](https://www.baselane.com/resources/best-ai-lease-abstraction-tools) — table stakes for lease automation software
- [OCR Contract Management: Strategies (Sirion)](https://www.sirion.ai/library/contract-management/ocr-contract-management/) — human-in-the-loop validation patterns
- [How to Automate Passport Data Extraction (Klippa)](https://www.klippa.com/en/blog/information/passport-data-extraction/) — passport OCR field expectations
- [10 Property Manager Pain Points (Beagle)](https://www.joinbeagle.com/post/10-property-manager-pain-points) — landlord pain points informing anti-features
- [python-telegram-bot ConversationHandler docs v22.7](https://docs.python-telegram-bot.org/en/stable/examples.html) — FSM capabilities
- [Contract AI Reliability Problem (Artificial Lawyer, Oct 2025)](https://www.artificiallawyer.com/2025/10/23/contract-ais-reliability-problem-when-ai-gets-it-wrong/) — OCR correction flow necessity

---

*Feature research for: Telegram rental contract automation bot*
*Researched: 2026-03-24*
