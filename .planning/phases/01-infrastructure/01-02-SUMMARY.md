---
phase: 01-infrastructure
plan: 02
subsystem: infra
tags: [python, logging, python-dotenv, stdlib-logging, libreoffice, docx]

# Dependency graph
requires:
  - phase: 01-01
    provides: requirements.txt (python-dotenv, docxtpl pinned), storage/ directory tree, main.py skeleton
provides:
  - Typed config module (config.py) loading env vars from .env with validation and fail-fast
  - Dual-output logger (logger.py) with console + rotating file handler (5MB/3 backups)
  - LibreOffice headless verification script with font substitution detection (scripts/verify_libreoffice.py)
  - Updated main.py using config.validate() and structured logger instead of print()
affects: [02-database, 03-templates, 04-ocr, 05-bot, 06-testing]

# Tech tracking
tech-stack:
  added:
    - stdlib logging (RotatingFileHandler — no structlog needed)
    - python-dotenv (load_dotenv in config.py)
    - python-docx (transitive via docxtpl — used in verify script)
  patterns:
    - "All modules call get_logger(__name__) for named loggers — never use logging.getLogger() directly in app code"
    - "configure_logging() called once at startup in main.py before any other imports use logging"
    - "config.validate() called inside main() not at module load — allows import without SystemExit"

key-files:
  created:
    - config.py
    - logger.py
    - scripts/__init__.py
    - scripts/verify_libreoffice.py
  modified:
    - main.py

key-decisions:
  - "Used stdlib logging (not structlog) — structlog is not in requirements.txt; stdlib RotatingFileHandler is sufficient"
  - "config.validate() placed inside main() not at module level — importing config does not trigger SystemExit, only running the bot does"
  - "verify_libreoffice.py uses tempfile.TemporaryDirectory() for automatic cleanup — no manual finally cleanup needed"
  - "Font substitution check looks for 'substitut', 'FontName', 'font replacement', 'cannot open' in LibreOffice stdout+stderr"

patterns-established:
  - "Named logger pattern: get_logger(__name__) in each module"
  - "Fail-fast validation: config.validate() called early in main() before any I/O"
  - "LibreOffice flags: always --headless --norestore --nofirststartwizard for headless stability"

requirements-completed: [INFR-01, INFR-04]

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 01 Plan 02: Config, Logger, and LibreOffice Verification Summary

**stdlib logging with dual console+file output (RotatingFileHandler), typed env config with validate(), and LibreOffice headless font-substitution detection script**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T06:42:51Z
- **Completed:** 2026-03-24T06:44:27Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- config.py exports BOT_TOKEN, ANTHROPIC_KEY, LOG_LEVEL, STORAGE_DIR, LOGS_DIR, DB_PATH, PERSISTENCE_PATH and a validate() function with clear error messages and sys.exit(1)
- logger.py exports configure_logging() (dual console+file with RotatingFileHandler 5MB/3 backups) and get_logger() — all stdlib, no external logging library
- scripts/verify_libreoffice.py detects font substitution via LibreOffice stderr/stdout analysis, recommends fonts-crosextra-carlito/caladea install, uses --norestore --nofirststartwizard flags, 60s timeout
- main.py rewritten to use config.validate() and structured logger — no bare print() calls remain

## Task Commits

Each task was committed atomically:

1. **Task 1: Create config.py and logger.py** - `87dd978` (feat)
2. **Task 2: Create verify_libreoffice.py and update main.py** - `2b7cdb4` (feat)

**Plan metadata:** _(docs commit to follow)_

## Files Created/Modified
- `config.py` - Typed env config with BOT_TOKEN, ANTHROPIC_KEY, LOG_LEVEL, STORAGE_DIR, LOGS_DIR, DB_PATH, PERSISTENCE_PATH and validate()
- `logger.py` - Dual-output logging: StreamHandler (stdout) + RotatingFileHandler (5MB, 3 backups); exports configure_logging() and get_logger()
- `scripts/__init__.py` - Empty package init for scripts directory
- `scripts/verify_libreoffice.py` - Headless LibreOffice PDF conversion test with font substitution detection and remediation advice
- `main.py` - Updated entry point: configure_logging() at startup, config.validate() in main(), _log.info() for startup message

## Decisions Made
- Used stdlib `logging` with `RotatingFileHandler` — structlog is not in requirements.txt; stdlib is sufficient and adds no new dependency
- `config.validate()` is inside `main()` not at module level — this allows `import config` and `import main` to succeed without a .env file, enabling test imports and script imports
- `verify_libreoffice.py` uses `tempfile.TemporaryDirectory()` for automatic cleanup (no manual finally block needed for temp files)
- Font substitution detection checks both stdout and stderr from LibreOffice — warnings can appear in either stream

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required at this stage.

For production server setup: run `python scripts/verify_libreoffice.py` after installing LibreOffice. If font substitution warnings appear, install: `sudo apt-get install fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation`

## Known Stubs

None - all modules are fully wired. config.py reads real env vars, logger.py writes to real files, main.py calls real validation. No placeholder data flows anywhere.

## Next Phase Readiness
- Phase 02 (database): can import `from config import DB_PATH, STORAGE_DIR` for SQLAlchemy engine setup
- Phase 03 (templates): can import `from config import TEMPLATES_DIR, CONTRACTS_DIR` for template path resolution
- Phase 04 (OCR): can import `from config import ANTHROPIC_KEY` for Claude API client initialization
- Phase 05 (bot): can import `from config import BOT_TOKEN, PERSISTENCE_PATH` for ApplicationBuilder setup
- All phases: `from logger import get_logger` pattern ready to use; configure_logging() already called in main.py

---
*Phase: 01-infrastructure*
*Completed: 2026-03-24*
