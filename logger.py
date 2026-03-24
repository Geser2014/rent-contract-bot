"""Logging setup — dual output: console + rotating file."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _ensure_log_dir(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)


def configure_logging(log_level: str = "INFO", log_dir: Path | None = None) -> None:
    """Configure root logger with console + file handlers.

    Call once at startup before any other imports use logging.
    """
    if log_dir is None:
        log_dir = Path("storage") / "logs"
    _ensure_log_dir(log_dir)

    level = getattr(logging, log_level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    file_handler = RotatingFileHandler(
        log_dir / "bot.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if called multiple times
    if not root.handlers:
        root.addHandler(console_handler)
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call configure_logging() before first use."""
    return logging.getLogger(name)
