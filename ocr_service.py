"""OCR service for Russian internal passport recognition.

Public API:
    PASSPORT_FIELDS: list[str]                                        -- ordered list of 10 field names
    extract_passport_fields(page1_bytes, page2_bytes) -> dict[str, str]  -- async, calls Claude Vision
    get_unclear_fields(fields) -> list[str]                           -- fields whose value is 'UNCLEAR'
    format_ocr_summary(fields) -> str                                 -- Telegram-ready Russian summary

Usage:
    fields = await extract_passport_fields(page1_bytes, page2_bytes)
    unclear = get_unclear_fields(fields)
    summary = format_ocr_summary(fields)

The service is Telegram-agnostic and fully testable without a running bot.
Ambiguous or illegible fields are returned as the exact string 'UNCLEAR' (uppercase).
"""
import asyncio
import base64
import io
import logging

import anthropic
from PIL import Image

import config

logger = logging.getLogger(__name__)

_CLAUDE_MODEL = "claude-sonnet-4-6"

# Module-level singleton — created once, reused for every OCR call.
_CLIENT = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_KEY)

# Ordered list of all 10 passport fields. Order matches ContractData declaration.
PASSPORT_FIELDS = [
    "tenant_full_name",
    "tenant_dob",
    "tenant_birthplace",
    "tenant_gender",
    "passport_series",
    "passport_number",
    "passport_issued_date",
    "passport_issued_by",
    "passport_division_code",
    "tenant_address",
]

_FIELD_LABELS = {
    "tenant_full_name":       "ФИО",
    "tenant_dob":             "Дата рождения",
    "tenant_birthplace":      "Место рождения",
    "tenant_gender":          "Пол",
    "passport_series":        "Серия",
    "passport_number":        "Номер",
    "passport_issued_date":   "Дата выдачи",
    "passport_issued_by":     "Кем выдан",
    "passport_division_code": "Код подразделения",
    "tenant_address":         "Адрес регистрации",
}

_PASSPORT_TOOL = {
    "name": "extract_passport_fields",
    "description": (
        "Extract all required fields from a Russian internal passport. "
        "Use exactly 'UNCLEAR' (uppercase) for any field that is illegible, "
        "blurry, partially occluded, or ambiguous."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tenant_full_name":        {"type": "string", "description": "ФИО полностью (Фамилия Имя Отчество)"},
            "tenant_dob":              {"type": "string", "description": "Дата рождения в формате ДД.ММ.ГГГГ"},
            "tenant_birthplace":       {"type": "string", "description": "Место рождения"},
            "tenant_gender":           {"type": "string", "description": "Пол: М или Ж"},
            "passport_series":         {"type": "string", "description": "Серия паспорта (4 цифры)"},
            "passport_number":         {"type": "string", "description": "Номер паспорта (6 цифр)"},
            "passport_issued_date":    {"type": "string", "description": "Дата выдачи в формате ДД.ММ.ГГГГ"},
            "passport_issued_by":      {"type": "string", "description": "Кем выдан (наименование органа)"},
            "passport_division_code":  {"type": "string", "description": "Код подразделения в формате XXX-XXX"},
            "tenant_address":          {"type": "string", "description": "Адрес регистрации (со страницы прописки)"},
        },
        "required": [
            "tenant_full_name", "tenant_dob", "tenant_birthplace", "tenant_gender",
            "passport_series", "passport_number", "passport_issued_date",
            "passport_issued_by", "passport_division_code", "tenant_address",
        ],
    },
}

_SYSTEM_PROMPT = (
    "Ты — система распознавания паспортных данных. "
    "Читай данные точно как написано в документе. "
    "Если поле нечитаемо, размыто или частично закрыто — верни строку 'UNCLEAR'. "
    "Никогда не угадывай и не домысливай. "
    "Все 10 полей обязательны — используй 'UNCLEAR' если не можешь прочитать."
)


def _resize_image_bytes(raw_bytes: bytes, max_px: int = 1600) -> bytes:
    """Resize image so longest edge <= max_px. Returns JPEG bytes at quality=92.

    Synchronous — wrap with asyncio.to_thread() from async callers.
    Preserves aspect ratio via thumbnail(). No-op if image is already within bounds.
    """
    img = Image.open(io.BytesIO(raw_bytes))
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


async def extract_passport_fields(
    page1_bytes: bytes,
    page2_bytes: bytes,
) -> dict[str, str]:
    """Call Claude Vision with both passport pages. Returns 10-field dict.

    page1_bytes: main passport page (series, number, name, dob, issuer, etc.)
    page2_bytes: registration page (address).

    All values are strings. Fields the model cannot read confidently are 'UNCLEAR'.

    Resizes both images to max 1600px via asyncio.to_thread (Pillow is synchronous).
    Uses tool_use with forced tool_choice for deterministic structured output.
    Logs input_tokens and output_tokens at INFO level after every successful call.

    Raises anthropic.APIError on network or authentication failure.
    Raises ValueError if Claude does not return a tool_use block.
    """
    # Resize both images in a thread pool (Pillow is sync; must not block event loop)
    p1 = await asyncio.to_thread(_resize_image_bytes, page1_bytes)
    p2 = await asyncio.to_thread(_resize_image_bytes, page2_bytes)

    page1_b64 = base64.standard_b64encode(p1).decode()
    page2_b64 = base64.standard_b64encode(p2).decode()

    response = await _CLIENT.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        tools=[_PASSPORT_TOOL],
        tool_choice={"type": "tool", "name": "extract_passport_fields"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": page1_b64,
                        },
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": page2_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Первое изображение — главная страница паспорта "
                            "(серия, номер, ФИО, дата рождения, место рождения, пол, "
                            "кем выдан, дата выдачи, код подразделения). "
                            "Второе изображение — страница с пропиской (адрес регистрации). "
                            "Вызови инструмент extract_passport_fields со всеми 10 полями."
                        ),
                    },
                ],
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_passport_fields":
            logger.info(
                "OCR complete. input_tokens=%d output_tokens=%d",
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return block.input  # type: ignore[return-value]

    raise ValueError(
        f"Claude did not return tool_use block. "
        f"stop_reason={response.stop_reason!r} "
        f"content={response.content!r}"
    )


def get_unclear_fields(fields: dict[str, str]) -> list[str]:
    """Return list of field names whose value is 'UNCLEAR'.

    Comparison is case-insensitive and strips surrounding whitespace.
    Field order matches PASSPORT_FIELDS.
    """
    return [k for k in PASSPORT_FIELDS if fields.get(k, "").strip().upper() == "UNCLEAR"]


def format_ocr_summary(fields: dict[str, str]) -> str:
    """Format OCR result as a Telegram-ready Russian message.

    Each field is shown on its own line as "*Label:* value".
    UNCLEAR values are suffixed with " ⚠️ UNCLEAR" to draw attention.
    The header line is separated from the field list by a blank line.

    Returns a multi-line string suitable for Telegram MarkdownV1 parse_mode.
    """
    lines = ["*Данные паспорта — проверьте внимательно:*\n"]
    for key, label in _FIELD_LABELS.items():
        value = fields.get(key, "UNCLEAR")
        if value.strip().upper() == "UNCLEAR":
            value = value + " ⚠️ UNCLEAR"
        lines.append(f"*{label}:* {value}")
    return "\n".join(lines)
