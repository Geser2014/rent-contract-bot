---
phase: 01-infrastructure
plan: 01
subsystem: infra
tags: [python, python-telegram-bot, anthropic, docxtpl, sqlalchemy, pydantic, ruff, pytest]

# Dependency graph
requires: []
provides:
  - Pinned runtime dependencies in requirements.txt (9 packages, no version ranges)
  - Dev dependencies in requirements-dev.txt (pytest, pytest-asyncio, ruff)
  - Ruff linter configuration in pyproject.toml with py310 target
  - Storage directory tree (storage/templates/Г39, storage/templates/Г38, storage/contracts, storage/logs)
  - Environment variable documentation in .env.example
  - main.py entry point skeleton with fail-fast startup validation
affects: [02-database, 03-templates, 04-ocr, 05-bot, 06-testing]

# Tech tracking
tech-stack:
  added:
    - python-telegram-bot==22.7
    - anthropic==0.86.0
    - docxtpl==0.20.2
    - SQLAlchemy==2.0.48
    - aiosqlite==0.22.1
    - pydantic==2.12.5
    - python-dotenv==1.1.0
    - httpx==0.28.1
    - Pillow==11.2.1
    - pytest==8.3.5
    - pytest-asyncio==0.25.3
    - ruff==0.11.2
  patterns:
    - "Fail-fast startup validation: validate env vars and directory structure before any bot logic"
    - "load_dotenv() called before import os to ensure env vars are set at module level"

key-files:
  created:
    - requirements.txt
    - requirements-dev.txt
    - pyproject.toml
    - .gitignore
    - .env.example
    - main.py
    - storage/templates/Г39/.gitkeep
    - storage/templates/Г38/.gitkeep
    - storage/contracts/.gitkeep
    - storage/logs/.gitkeep
  modified: []

key-decisions:
  - "Pinned all versions with ==, no ranges, to ensure reproducible installs across dev and prod"
  - "storage/contracts and storage/logs are .gitignored (generated output); .gitkeep files force-added to commit empty dirs"
  - "main.py uses sys.exit(1) with print to stderr on missing env vars — never a Python traceback"

patterns-established:
  - "Fail-fast pattern: all environment and directory validation happens at module load before bot code runs"
  - "Cyrillic directory names (Г39, Г38) match business domain exactly to avoid translation errors"

requirements-completed: [INFR-01]

# Metrics
duration: 2min
completed: 2026-03-24
---

# Phase 01 Plan 01: Project Scaffold Summary

**Python project scaffold with 9 pinned runtime deps, ruff linter config, storage directory tree (Г39/Г38 templates), and a fail-fast main.py that exits cleanly on missing env vars**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T06:38:51Z
- **Completed:** 2026-03-24T06:40:53Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- requirements.txt with 9 exact-pinned packages and requirements-dev.txt with pytest/ruff for testing and linting
- pyproject.toml configuring ruff (py310 target, line-length=100) and pytest asyncio_mode=auto
- storage/ directory tree with Г39 and Г38 template subdirectories committed via .gitkeep files
- main.py entry point that validates TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, and storage directories at startup — exits code 1 with readable error if anything is missing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pinned dependency files and linter config** - `6b2c6a7` (chore)
2. **Task 2: Create storage directory tree, .env.example, and main.py skeleton** - `9348133` (feat)

**Plan metadata:** _(docs commit to follow)_

## Files Created/Modified
- `requirements.txt` - 9 pinned runtime dependencies (python-telegram-bot, anthropic, docxtpl, SQLAlchemy, aiosqlite, pydantic, python-dotenv, httpx, Pillow)
- `requirements-dev.txt` - Dev/test deps extending requirements.txt (pytest, pytest-asyncio, ruff)
- `pyproject.toml` - Ruff linter config (py310, line-length=100, E/F/W/I rules) and pytest asyncio config
- `.gitignore` - Excludes .env, *.db, storage/contracts/, storage/logs/, build artifacts
- `.env.example` - Documents TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, STORAGE_DIR, LOG_LEVEL
- `main.py` - Bot entry point with validate_environment() and fail-fast sys.exit(1) on missing config
- `storage/templates/Г39/.gitkeep` - Commits Г39 template directory
- `storage/templates/Г38/.gitkeep` - Commits Г38 template directory
- `storage/contracts/.gitkeep` - Commits contracts output directory (force-added, dir is gitignored)
- `storage/logs/.gitkeep` - Commits logs directory (force-added, dir is gitignored)

## Decisions Made
- Pinned all versions with `==` (no `>=` or ranges) to ensure reproducible installs
- `storage/contracts/` and `storage/logs/` are .gitignored since they hold generated output; `.gitkeep` files were force-added with `git add -f` to commit the empty directory structure
- `main.py` uses `sys.exit(1)` with `print(..., file=sys.stderr)` — never raises an unhandled exception that would show a traceback

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `storage/contracts/.gitkeep` and `storage/logs/.gitkeep` were blocked by .gitignore (which excludes `storage/contracts/` and `storage/logs/`). Resolved by using `git add -f` to force-add the .gitkeep placeholder files. This is correct behavior: the directories need to exist in the repo, but their runtime contents should remain gitignored.

## User Setup Required

None - no external service configuration required at this stage. Users will need to copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN` and `ANTHROPIC_API_KEY` before running the bot (enforced by main.py's fail-fast validation).

## Next Phase Readiness
- Phase 02 (database) can proceed: SQLAlchemy and aiosqlite are pinned and ready to use
- Phase 03 (templates): storage/templates/Г39 and Г38 directories exist for DOCX template placement
- All phases: ruff linting configured, pytest asyncio_mode=auto ready for async test authoring

---
*Phase: 01-infrastructure*
*Completed: 2026-03-24*
