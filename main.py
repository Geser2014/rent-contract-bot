"""Rent Contract Bot — entry point."""
from dotenv import load_dotenv

# Load .env FIRST — before any other imports that read env vars
load_dotenv()

import config  # noqa: E402
from logger import configure_logging, get_logger  # noqa: E402
from telegram.ext import Application, PicklePersistence  # noqa: E402
from bot.handlers.conversation import build_conversation_handler  # noqa: E402

configure_logging(log_level=config.LOG_LEVEL, log_dir=config.LOGS_DIR)
_log = get_logger(__name__)


def main() -> None:
    config.validate()
    _log.info("Environment validated. Bot starting...")

    persistence = PicklePersistence(filepath=str(config.PERSISTENCE_PATH))
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .persistence(persistence)
        .concurrent_updates(False)
        .build()
    )
    app.add_handler(build_conversation_handler())
    _log.info("Bot ready. Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
