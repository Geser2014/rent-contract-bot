"""Handler for /stats command — contract statistics."""
import json as _json
from pathlib import Path

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

import config
import database

_AUTH_FILE = config.STORAGE_DIR / "authorized_users.json"


def _is_authorized(user_id: int) -> bool:
    if not config.BOT_PASSWORD:
        return True
    if _AUTH_FILE.exists():
        return user_id in set(_json.loads(_AUTH_FILE.read_text()))
    return False

_MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show contract statistics."""
    if not _is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа. Используйте /start для авторизации.")
        return
    s = await database.get_stats()

    lines = [f"📊 *Статистика договоров*\n\nВсего: *{s['total']}*\n"]

    # By group
    if s["by_group"]:
        lines.append("*По группам:*")
        for group, count in s["by_group"]:
            pct = round(count / s["total"] * 100) if s["total"] else 0
            lines.append(f"  {group}: {count} ({pct}%)")
        lines.append("")

    # By month
    if s["by_month"]:
        lines.append(f"*По месяцам ({s['year']}):*")
        for month, count in s["by_month"]:
            name = _MONTH_NAMES.get(month, str(month))
            lines.append(f"  {name}: {count}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def get_stats_handlers() -> list:
    return [CommandHandler("stats", cmd_stats)]
