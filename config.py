"""Application configuration — loads and validates environment variables."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)



# --- Required ---
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# --- Optional with defaults ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", "storage"))

# --- Derived paths ---
TEMPLATES_DIR: Path = STORAGE_DIR / "templates"
CONTRACTS_DIR: Path = STORAGE_DIR / "contracts"
LOGS_DIR: Path = STORAGE_DIR / "logs"
DB_PATH: Path = STORAGE_DIR / "contracts.db"
PERSISTENCE_PATH: Path = STORAGE_DIR / "conversation_state.pkl"


def validate() -> None:
    """Raise SystemExit with a human-readable message if config is invalid."""
    errors: list[str] = []
    if not BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    if not ANTHROPIC_KEY:
        errors.append("ANTHROPIC_API_KEY is not set")
    if not (TEMPLATES_DIR / "Подольская 39").is_dir():
        errors.append(f"Missing directory: {TEMPLATES_DIR / 'Подольская 39'}")
    if not (TEMPLATES_DIR / "Подольская 38").is_dir():
        errors.append(f"Missing directory: {TEMPLATES_DIR / 'Подольская 38'}")
    if errors:
        print("ERROR: Configuration problems:\n  " + "\n  ".join(errors), file=sys.stderr)
        sys.exit(1)
