"""Rent Contract Bot — entry point."""
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before accessing environment variables
load_dotenv()

import os  # noqa: E402 — must be after load_dotenv


def validate_environment() -> None:
    """Validate required environment variables and directory structure."""
    missing = []
    for var in ("TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY"):
        if not os.getenv(var):
            missing.append(var)
    if missing:
        print(
            f"ERROR: Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in the values.",
            file=sys.stderr,
        )
        sys.exit(1)

    base = Path(__file__).parent / "storage" / "templates"
    for group in ("Г39", "Г38"):
        if not (base / group).is_dir():
            print(
                f"ERROR: Required directory missing: storage/templates/{group}\n"
                f"Run: mkdir -p storage/templates/Г39 storage/templates/Г38",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    validate_environment()
    print("Environment validated. Bot starting...")
    # Bot Application setup goes here in Phase 5
