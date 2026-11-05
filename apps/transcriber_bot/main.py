"""Production Telegram bot: voice message in, Russian transcription out."""

from __future__ import annotations

import asyncio
import html
import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Audio,
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Message,
)
from apps.transcriber_bot.storage import get_language, init_db, recent_transcriptions, save_transcription, set_language

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
TRANSCRIPTION_MODEL = os.environ.get("TRANSCRIPTION_MODEL", "openai/whisper-large-v3-turbo")
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "https://telegram.org")
MAX_FILE_BYTES = int(os.environ.get("MAX_TRANSCRIPTION_FILE_MB", "20")) * 1024 * 1024
RATE_LIMIT_COUNT = int(os.environ.get("TRANSCRIPTION_RATE_LIMIT", "10"))
RATE_LIMIT_WINDOW = 60 * 60
MAX_TELEGRAM_TEXT = 4096

router = Router()
processing_slots = asyncio.Semaphore(2)
recent_requests: dict[int, deque[float]] = defaultdict(deque)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Как это работает", callback_data="help")],
            [InlineKeyboardButton(text="Приватность", callback_data="privacy")],
        ]
    )


def reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎙 Новая расшифровка"), KeyboardButton(text="🕘 История")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🔒 Приватность")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Отправьте голосовое сообщение",
    )


def language_keyboard(language: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=("✅ Русский" if language == "ru" else "Русский"), callback_data="lang:ru")],
            [InlineKeyboardButton(text=("✅ Автоопределение" if language == "auto" else "Автоопределение"), callback_data="lang:auto")],
        ]
    )


def is_rate_limited(user_id: int) -> bool:
    now = time.monotonic()
    entries = recent_requests[user_id]
    while entries and now - entries[0] > RATE_LIMIT_WINDOW:
        entries.popleft()
    if len(entries) >= RATE_LIMIT_COUNT:
        return True
    entries.append(now)
    return False


def split_text(text: str, limit: int = MAX_TELEGRAM_TEXT) -> list[str]:
    if not text:
        return ["Не удалось получить текст из записи."]
    return [text[offset : offset + limit] for offset in range(0, len(text), limit)]


def audio_details(message: Message) -> tuple[str, str, int | None] | None:
    voice: Audio | None = message.voice or message.audio
    if not voice:
        return None
    filename = getattr(voice, "file_name", None) or f"voice-{voice.file_unique_id}.ogg"
    mime_type = getattr(voice, "mime_type", None) or "audio/ogg"
    return voice.file_id, filename, voice.file_size


async def transcribe_file(path: Path, filename: str, language: str = "ru") -> str:
    if not OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    with path.open("rb") as audio:
        response = await _post_transcription(audio, filename, _mime_for(filename), language)
    if response.status_code >= 400:
        detail = response.text[:400].replace("\n", " ")
        raise RuntimeError(f"OpenRouter returned {response.status_code}: {detail}")
    payload = response.json()
    text = str(payload.get("text") or "").strip()
    if not text:
        raise RuntimeError("OpenRouter returned empty transcription")
    return text


async def _post_transcription(audio: Any, filename: str, mime_type: str, language: str = "ru") -> httpx.Response:
    data = {
        "model": TRANSCRIPTION_MODEL,
        "response_format": "json",
    }
    if language != "auto":
        data["language"] = language
    files = {"file": (filename, audio, mime_type)}
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer": WEB_BASE_URL,
        "X-Title": "VoiceType Russian transcription bot",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=20.0)) as client:
        return await client.post(f"{OPENROUTER_BASE_URL}/audio/transcriptions", headers=headers, data=data, files=files)


def _mime_for(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
    }.get(suffix, "application/octet-stream")


async def send_transcript(message: Message, text: str) -> None:
    for part in split_text(text):
        await message.answer(html.escape(part), disable_web_page_preview=True)


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "<b>VoiceType</b>\n\n"
        "Отправьте голосовое сообщение — я превращу его в аккуратный русский текст.\n\n"
        "<i>Аудио обрабатывается только для текущей расшифровки и затем удаляется.</i>",
        reply_markup=reply_menu(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>Как пользоваться</b>\n\n"
        "1. Нажмите и удерживайте кнопку записи голосового.\n"
        "2. Отправьте сообщение в этот чат.\n"
        "3. Через несколько секунд получите текст.\n\n"
        "Поддерживаются голосовые сообщения и аудиофайлы до 20 МБ.",
        reply_markup=reply_menu(),
    )


@router.message(Command("menu"))
@router.message(F.text.in_({"❓ Помощь", "Помощь"}))
async def menu_command(message: Message) -> None:
    await help_command(message)


@router.message(Command("new"))
@router.message(F.text.in_({"🎙 Новая расшифровка", "Новая расшифровка"}))
async def new_transcription(message: Message) -> None:
    await message.answer(
        "Готово. Отправьте голосовое сообщение или аудиофайл — я верну текст.",
        reply_markup=reply_menu(),
    )


@router.message(Command("privacy"))
@router.message(F.text.in_({"🔒 Приватность", "Приватность"}))
async def privacy_command(message: Message) -> None:
    await message.answer(
        "<b>Приватность</b>\n\n"
        "Аудио временно передаётся в OpenRouter для распознавания и удаляется после обработки.\n"
        "В боте сохраняются только последние 20 текстовых расшифровок, чтобы была доступна история.\n\n"
        "Не отправляйте секретные данные, если для них не согласован внешний AI-провайдер.",
        reply_markup=reply_menu(),
    )


@router.message(Command("settings"))
@router.message(F.text.in_({"⚙️ Настройки", "Настройки"}))
async def settings_command(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else message.chat.id
    language = await get_language(user_id)
    label = "русский" if language == "ru" else "автоопределение"
    await message.answer(
        f"<b>Настройки</b>\n\nЯзык распознавания: <b>{label}</b>\n\nВыберите режим:",
        reply_markup=language_keyboard(language),
    )


@router.callback_query(F.data.startswith("lang:"))
async def language_callback(callback: CallbackQuery) -> None:
    await callback.answer("Настройка сохранена")
    if not callback.from_user or not callback.message:
        return
    language = callback.data.split(":", 1)[1]
    await set_language(callback.from_user.id, language)
    label = "русский" if language == "ru" else "автоопределение"
    await callback.message.edit_text(
        f"<b>Настройки</b>\n\nЯзык распознавания: <b>{label}</b>",
        reply_markup=language_keyboard(language),
    )


@router.message(Command("history"))
@router.message(F.text.in_({"🕘 История", "История"}))
async def history_command(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else message.chat.id
    rows = await recent_transcriptions(user_id)
    if not rows:
        await message.answer("История пока пуста. Отправьте первое голосовое сообщение.", reply_markup=reply_menu())
        return
    lines = ["<b>Последние расшифровки</b>", ""]
    for created_at, text in rows:
        preview = html.escape(text.replace("\n", " ")[:240])
        lines.append(f"<i>{html.escape(created_at[5:16])}</i>\n{preview}")
    await message.answer("\n\n".join(lines), reply_markup=reply_menu())


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "<b>Как пользоваться</b>\n\n"
            "Отправьте голосовое сообщение или аудиофайл — бот распознает русскую речь и вернёт текст.\n\n"
            "Лимит: 20 МБ на файл.",
            reply_markup=main_keyboard(),
        )


@router.callback_query(F.data == "privacy")
async def privacy_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "<b>Приватность</b>\n\n"
            "Файл временно передаётся в OpenRouter для распознавания."
            " После завершения обработки локальная копия удаляется.\n\n"
            "Не отправляйте секретные данные, если для них не согласован внешний AI-провайдер.",
            reply_markup=main_keyboard(),
        )


@router.message(F.voice | F.audio)
async def transcribe_message(message: Message, bot: Bot) -> None:
    details = audio_details(message)
    if not details:
        return
    file_id, filename, file_size = details
    if file_size and file_size > MAX_FILE_BYTES:
        await message.answer("Файл больше 20 МБ. Отправьте более короткое голосовое сообщение.")
        return
    if is_rate_limited(message.from_user.id if message.from_user else 0):
        await message.answer("Лимит расшифровок на час исчерпан. Попробуйте немного позже.")
        return
    user_id = message.from_user.id if message.from_user else message.chat.id
    language = await get_language(user_id)

    status = await message.answer("<b>Принято</b>\nСкачиваю аудио…")
    try:
        async with processing_slots:
            await status.edit_text("<b>В работе</b>\nРаспознаю русскую речь…")
            telegram_file = await bot.get_file(file_id)
            if not telegram_file.file_path:
                raise RuntimeError("Telegram did not return a file path")
            with TemporaryDirectory(prefix="voicetype-") as temp_dir:
                target = Path(temp_dir) / Path(filename).name
                await bot.download_file(telegram_file.file_path, destination=target)
                transcript = await transcribe_file(target, target.name, language)
        await save_transcription(user_id, message.chat.id, transcript)
        await status.delete()
        await send_transcript(message, transcript)
    except Exception:
        logging.exception("transcription failed for chat %s", message.chat.id)
        await status.edit_text(
            "<b>Не удалось расшифровать</b>\n\n"
            "Попробуйте отправить голосовое ещё раз. Если ошибка повторяется, проверьте длительность и размер записи."
        )


@router.message()
async def unsupported_message(message: Message) -> None:
    await message.answer("Отправьте голосовое сообщение — я превращу его в текст.", reply_markup=reply_menu())


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is required")

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    await init_db()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть VoiceType"),
            BotCommand(command="help", description="Как пользоваться"),
            BotCommand(command="new", description="Новая расшифровка"),
            BotCommand(command="history", description="История расшифровок"),
            BotCommand(command="settings", description="Настройки языка"),
            BotCommand(command="privacy", description="Приватность"),
            BotCommand(command="menu", description="Показать меню"),
        ]
    )
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
