"""Production Telegram bot: voice message in, Russian transcription out."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import math
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
    LabeledPrice,
    PreCheckoutQuery,
    ReplyKeyboardMarkup,
    Document,
    Message,
    Video,
)
from apps.transcriber_bot.storage import (
    get_language,
    get_mode,
    init_db,
    recent_transcriptions,
    save_transcription,
    set_language,
    set_mode,
)
from apps.transcriber_bot.storage import charge_usage, get_balance, record_payment, refund_usage

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
TRANSCRIPTION_MODEL = os.environ.get("TRANSCRIPTION_MODEL", "openai/whisper-large-v3-turbo")
CONFERENCE_MODEL = os.environ.get("CONFERENCE_MODEL", "elevenlabs/scribe-v2")
SUMMARY_MODEL = os.environ.get("SUMMARY_MODEL", "openai/gpt-4o-mini")
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "https://telegram.org")
MAX_FILE_BYTES = int(os.environ.get("MAX_TRANSCRIPTION_FILE_MB", "20")) * 1024 * 1024
RATE_LIMIT_COUNT = int(os.environ.get("TRANSCRIPTION_RATE_LIMIT", "10"))
RATE_LIMIT_WINDOW = 60 * 60
MAX_TELEGRAM_TEXT = 4096
FREE_USER_IDS = {
    int(value.strip())
    for value in os.environ.get("FREE_USER_IDS", os.environ.get("ALLOWED_USER_IDS", "")).split(",")
    if value.strip().isdigit()
}
SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".webm", ".ogg", ".flac", ".aac"}
SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

PLANS = {
    "monthly_5": {"title": "5 часов + 60 AI-действий / месяц", "stars": 235, "minutes": 300, "actions": 60, "monthly": True},
    "monthly_12": {"title": "12 часов + 300 AI-действий / месяц", "stars": 475, "minutes": 720, "actions": 300, "monthly": True},
    "monthly_40": {"title": "40 часов + 1000 AI-действий / месяц", "stars": 1425, "minutes": 2400, "actions": 1000, "monthly": True},
    "one_1": {"title": "1 час + 60 AI-действий", "stars": 235, "minutes": 60, "actions": 60, "monthly": False},
    "one_3": {"title": "3 часа + 180 AI-действий", "stars": 475, "minutes": 180, "actions": 180, "monthly": False},
    "one_10": {"title": "10 часов + 600 AI-действий", "stars": 1425, "minutes": 600, "actions": 600, "monthly": False},
}

router = Router()
processing_slots = asyncio.Semaphore(2)
recent_requests: dict[int, deque[float]] = defaultdict(deque)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎙 Новая расшифровка", callback_data="new"),
                InlineKeyboardButton(text="🕘 История", callback_data="history"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
                InlineKeyboardButton(text="🔒 Приватность", callback_data="privacy"),
            ],
            [InlineKeyboardButton(text="🗣 Конференция и summary", callback_data="conference")],
            [InlineKeyboardButton(text="💳 Тарифы и оплата", callback_data="plans")],
            [InlineKeyboardButton(text="💰 Мой баланс", callback_data="balance")],
            [InlineKeyboardButton(text="❓ Как пользоваться", callback_data="help")],
        ]
    )


def menu_text() -> str:
    return (
        "<b>VoiceType</b>\n\n"
        "Отправьте голосовое сообщение — я превращу его в аккуратный текст.\n\n"
        "Выберите раздел или сразу отправьте запись:"
    )


def is_free_user(user_id: int) -> bool:
    return user_id in FREE_USER_IDS


def plans_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="5 ч + 60 AI / месяц — 235 ⭐", callback_data="buy:monthly_5")],
            [InlineKeyboardButton(text="12 ч + 300 AI / месяц — 475 ⭐", callback_data="buy:monthly_12")],
            [InlineKeyboardButton(text="40 ч + 1000 AI / месяц — 1425 ⭐", callback_data="buy:monthly_40")],
            [InlineKeyboardButton(text="1 ч + 60 AI — 235 ⭐", callback_data="buy:one_1")],
            [InlineKeyboardButton(text="3 ч + 180 AI — 475 ⭐", callback_data="buy:one_3")],
            [InlineKeyboardButton(text="10 ч + 600 AI — 1425 ⭐", callback_data="buy:one_10")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="menu")],
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


def mode_keyboard(mode: str) -> InlineKeyboardMarkup:
    def label(value: str, text: str) -> str:
        return f"✅ {text}" if mode == value else text

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label("quick", "Быстрая расшифровка"), callback_data="mode:quick")],
            [InlineKeyboardButton(text=label("conference", "По ролям"), callback_data="mode:conference")],
            [InlineKeyboardButton(text=label("summary", "По ролям + summary"), callback_data="mode:summary")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="menu")],
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


def audio_details(message: Message) -> tuple[str, str, int | None, bool, int | None] | None:
    media: Audio | Document | Video | None = message.voice or message.audio or message.document or message.video
    if not media:
        return None
    is_video = bool(message.video) or Path(getattr(media, "file_name", "") or "").suffix.lower() in SUPPORTED_VIDEO_SUFFIXES
    fallback_suffix = ".mp4" if message.video else ".ogg"
    filename = getattr(media, "file_name", None) or f"recording-{media.file_unique_id}{fallback_suffix}"
    return media.file_id, filename, media.file_size, is_video, getattr(media, "duration", None)


async def extract_audio(path: Path, temp_dir: str) -> tuple[Path, str]:
    if path.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        return path, path.name
    output = Path(temp_dir) / "conference-audio.mp3"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-nostdin", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(output),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0 or not output.exists():
        detail = stderr.decode(errors="replace")[-300:].replace("\n", " ")
        raise RuntimeError(f"Не удалось извлечь аудио из видео: {detail}")
    return output, output.name


async def transcribe_file(path: Path, filename: str, language: str = "ru", conference: bool = False) -> str:
    if not OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    with path.open("rb") as audio:
        response = await _post_transcription(audio, filename, _mime_for(filename), language, conference)
    if response.status_code >= 400:
        detail = response.text[:400].replace("\n", " ")
        raise RuntimeError(f"OpenRouter returned {response.status_code}: {detail}")
    payload = response.json()
    text = _format_diarized(payload) if conference else str(payload.get("text") or "").strip()
    if not text:
        raise RuntimeError("OpenRouter returned empty transcription")
    return text


def _format_diarized(payload: dict[str, Any]) -> str:
    words = payload.get("words") or []
    turns: list[tuple[str, list[str]]] = []
    for item in words:
        word = str(item.get("word") or "").strip()
        speaker = str(item.get("speaker_label") or item.get("speaker") or "1")
        if not word:
            continue
        speaker = f"Спикер {speaker.replace('speaker_', '')}"
        if turns and turns[-1][0] == speaker:
            turns[-1][1].append(word)
        else:
            turns.append((speaker, [word]))
    if turns:
        return "\n\n".join(f"{speaker}: {' '.join(words)}" for speaker, words in turns)
    return str(payload.get("text") or "").strip()


async def _post_transcription(
    audio: Any, filename: str, mime_type: str, language: str = "ru", conference: bool = False
) -> httpx.Response:
    data = {
        "model": CONFERENCE_MODEL if conference else TRANSCRIPTION_MODEL,
        "response_format": "verbose_json" if conference else "json",
    }
    if language != "auto":
        data["language"] = language
    if conference:
        data["provider"] = json.dumps({"options": {"elevenlabs": {"diarize": True, "tag_audio_events": True}}})
    files = {"file": (filename, audio, mime_type)}
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "HTTP-Referer": WEB_BASE_URL,
        "X-Title": "VoiceType Russian transcription bot",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=20.0)) as client:
        return await client.post(f"{OPENROUTER_BASE_URL}/audio/transcriptions", headers=headers, data=data, files=files)


async def summarize_text(transcript: str) -> str:
    prompt = (
        "Сделай краткое структурированное summary встречи на русском языке. "
        "Выдели: 1) краткий итог, 2) ключевые решения, 3) задачи и ответственных, если они названы, "
        "4) открытые вопросы. Не выдумывай отсутствующие данные.\n\n" + transcript
    )
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "HTTP-Referer": WEB_BASE_URL, "X-Title": "VoiceType meeting summary"}
    payload = {
        "model": SUMMARY_MODEL,
        "messages": [
            {"role": "system", "content": "Ты аккуратный секретарь встреч."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=20.0)) as client:
        response = await client.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=payload)
    if response.status_code >= 400:
        detail = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"Summary failed {response.status_code}: {detail}")
    result = response.json()
    return str(result["choices"][0]["message"]["content"]).strip()


def _mime_for(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
    }.get(suffix, "application/octet-stream")


async def send_transcript(message: Message, text: str) -> None:
    for part in split_text(text):
        await message.answer(html.escape(part), disable_web_page_preview=True)


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        menu_text(),
        reply_markup=main_keyboard(),
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
    await message.answer(menu_text(), reply_markup=main_keyboard())


@router.message(Command("new"))
@router.message(F.text.in_({"🎙 Новая расшифровка", "Новая расшифровка"}))
async def new_transcription(message: Message) -> None:
    await message.answer(
        "Готово. Отправьте голосовое сообщение или аудиофайл — я верну текст.",
        reply_markup=reply_menu(),
    )


@router.callback_query(F.data == "menu")
async def menu_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(menu_text(), reply_markup=main_keyboard())


@router.callback_query(F.data == "plans")
async def plans_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "<b>Тарифы и оплата</b>\n\nВыберите пакет. Оплата проходит в Telegram Stars, минуты и AI-действия не сгорают для разовой покупки.",
            reply_markup=plans_keyboard(),
        )


@router.callback_query(F.data == "balance")
async def balance_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        minutes, actions = await get_balance(callback.from_user.id)
        await callback.message.edit_text(
            f"<b>Мой баланс</b>\n\nМинуты расшифровки: <b>{minutes}</b>\nAI-действия: <b>{actions}</b>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="plans")],
                    [InlineKeyboardButton(text="← Главное меню", callback_data="menu")],
                ]
            ),
        )


@router.callback_query(F.data.startswith("buy:"))
async def buy_callback(callback: CallbackQuery, bot: Bot) -> None:
    await callback.answer()
    if not callback.message:
        return
    code = callback.data.split(":", 1)[1]
    plan = PLANS.get(code)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    invoice_kwargs = {
        "chat_id": callback.message.chat.id,
        "title": plan["title"],
        "description": f"{plan['minutes'] // 60} ч расшифровки и {plan['actions']} AI-действий",
        "payload": f"plan:{code}",
        "currency": "XTR",
        "prices": [LabeledPrice(label=plan["title"], amount=plan["stars"])],
    }
    if plan["monthly"]:
        invoice_kwargs["subscription_period"] = 2592000
    await bot.send_invoice(**invoice_kwargs)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    code = query.invoice_payload.removeprefix("plan:")
    plan = PLANS.get(code)
    if not plan or query.total_amount != plan["stars"]:
        await query.answer(ok=False, error_message="Тариф недоступен. Откройте меню оплаты ещё раз.")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    if not message.successful_payment or not message.from_user:
        return
    payment = message.successful_payment
    code = payment.invoice_payload.removeprefix("plan:")
    plan = PLANS.get(code)
    if not plan:
        return
    saved = await record_payment(
        message.from_user.id,
        code,
        payment.telegram_payment_charge_id,
        payment.total_amount,
        plan["minutes"],
        plan["actions"],
    )
    if saved:
        await message.answer(
            f"✅ Оплата прошла. Начислено: {plan['minutes']} минут и {plan['actions']} AI-действий.",
            reply_markup=main_keyboard(),
        )


@router.message(Command("buy"))
async def buy_command(message: Message) -> None:
    await message.answer("<b>Тарифы и оплата</b>\n\nВыберите пакет:", reply_markup=plans_keyboard())


@router.message(Command("balance"))
async def balance_command(message: Message) -> None:
    if message.from_user:
        minutes, actions = await get_balance(message.from_user.id)
        await message.answer(f"<b>Баланс</b>\n\nМинуты: <b>{minutes}</b>\nAI-действия: <b>{actions}</b>", reply_markup=main_keyboard())


@router.message(Command("paysupport"))
async def paysupport_command(message: Message) -> None:
    await message.answer("По вопросам оплаты напишите владельцу бота и приложите скриншот платежа и Telegram user ID.")


@router.callback_query(F.data == "new")
async def new_callback(callback: CallbackQuery) -> None:
    await callback.answer("Жду голосовое")
    if callback.message:
        await callback.message.edit_text(
            "<b>Новая расшифровка</b>\n\nОтправьте голосовое, аудиофайл или запись Zoom — я верну текст.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Главное меню", callback_data="menu")]]
            ),
        )


@router.callback_query(F.data == "history")
async def history_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    rows = await recent_transcriptions(callback.from_user.id)
    if not rows:
        text = "<b>История</b>\n\nПока здесь пусто. Отправьте первое голосовое сообщение."
    else:
        lines = ["<b>Последние расшифровки</b>", ""]
        for created_at, transcript in rows:
            preview = html.escape(transcript.replace("\n", " ")[:240])
            lines.append(f"<i>{html.escape(created_at[5:16])}</i>\n{preview}")
        text = "\n\n".join(lines)
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Главное меню", callback_data="menu")]]
        ),
    )


@router.callback_query(F.data == "settings")
async def settings_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    language = await get_language(callback.from_user.id)
    mode = await get_mode(callback.from_user.id)
    label = "русский" if language == "ru" else "автоопределение"
    await callback.message.edit_text(
        f"<b>Настройки</b>\n\nЯзык: <b>{label}</b>\nРежим: <b>{mode_label(mode)}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=("✅ Русский" if language == "ru" else "Русский"), callback_data="lang:ru")],
                [InlineKeyboardButton(text=("✅ Автоопределение" if language == "auto" else "Автоопределение"), callback_data="lang:auto")],
                [InlineKeyboardButton(text="🎛 Изменить режим", callback_data="conference")],
                [InlineKeyboardButton(text="← Главное меню", callback_data="menu")],
            ]
        ),
    )


def mode_label(mode: str) -> str:
    return {
        "quick": "быстрая расшифровка",
        "conference": "по ролям",
        "summary": "по ролям + summary",
    }.get(mode, "быстрая расшифровка")


@router.callback_query(F.data == "conference")
async def conference_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    mode = await get_mode(callback.from_user.id)
    await callback.message.edit_text(
        "<b>Режим конференции</b>\n\n"
        "Выберите, как обрабатывать записи встреч и Zoom:\n\n"
        "<b>По ролям</b> — разделить текст по говорящим.\n"
        "<b>По ролям + summary</b> — разделить по говорящим и подготовить итоги, решения и задачи.",
        reply_markup=mode_keyboard(mode),
    )


@router.callback_query(F.data.startswith("mode:"))
async def mode_callback(callback: CallbackQuery) -> None:
    await callback.answer("Режим сохранён")
    if not callback.from_user or not callback.message:
        return
    mode = callback.data.split(":", 1)[1]
    await set_mode(callback.from_user.id, mode)
    await callback.message.edit_text(
        f"<b>Режим сохранён</b>\n\nТеперь записи будут обрабатываться так: <b>{mode_label(mode)}</b>.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎙 Отправить запись", callback_data="new")],
                [InlineKeyboardButton(text="← Главное меню", callback_data="menu")],
            ]
        ),
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
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎛 Режим конференции", callback_data="conference")],
                [InlineKeyboardButton(text="← Главное меню", callback_data="menu")],
            ]
        ),
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
            "Отправьте голосовое, аудиофайл или видеозапись Zoom — бот извлечёт речь и вернёт текст.\n\n"
            "Поддерживаются MP3, M4A, WAV, OGG, FLAC, AAC, MP4, MOV, MKV и AVI. Лимит: 20 МБ на файл.",
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


@router.message(F.voice | F.audio | F.document | F.video)
async def transcribe_message(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id if message.from_user else message.chat.id
    details = audio_details(message)
    if not details:
        return
    file_id, filename, file_size, is_video, duration = details
    suffix = Path(filename).suffix.lower()
    if message.document and suffix not in SUPPORTED_AUDIO_SUFFIXES | SUPPORTED_VIDEO_SUFFIXES:
        await message.answer(
            "Похоже, это не аудио- или видеофайл. Отправьте MP3, M4A, WAV, OGG, FLAC, AAC, MP4, MOV или MKV."
        )
        return
    if file_size and file_size > MAX_FILE_BYTES:
        await message.answer("Файл больше 20 МБ. Отправьте более короткое голосовое сообщение.")
        return
    if is_rate_limited(message.from_user.id if message.from_user else 0):
        await message.answer("Лимит расшифровок на час исчерпан. Попробуйте немного позже.")
        return
    language = await get_language(user_id)
    mode = await get_mode(user_id)
    conference = mode in {"conference", "summary"}
    minutes_to_charge = max(1, math.ceil(duration / 60)) if duration else 1
    actions_to_charge = 2 if mode == "summary" else 1 if mode == "conference" else 0
    if not is_free_user(user_id) and not await charge_usage(user_id, minutes_to_charge, actions_to_charge):
        await message.answer(
            "Недостаточно минут или AI-действий для этой операции.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="plans")]]
            ),
        )
        return
    charged = not is_free_user(user_id)

    status = await message.answer("<b>Принято</b>\nСкачиваю запись…")
    try:
        async with processing_slots:
            stage = "Распознаю речь и разделяю по говорящим…" if conference else "Распознаю русскую речь…"
            await status.edit_text(f"<b>В работе</b>\n{stage}")
            telegram_file = await bot.get_file(file_id)
            if not telegram_file.file_path:
                raise RuntimeError("Telegram did not return a file path")
            with TemporaryDirectory(prefix="voicetype-") as temp_dir:
                target = Path(temp_dir) / Path(filename).name
                await bot.download_file(telegram_file.file_path, destination=target)
                audio_path, audio_name = await extract_audio(target, temp_dir) if is_video else (target, target.name)
                transcript = await transcribe_file(audio_path, audio_name, language, conference)
            summary = await summarize_text(transcript) if mode == "summary" else ""
        await save_transcription(user_id, message.chat.id, transcript)
        await status.delete()
        await send_transcript(message, transcript)
        if summary:
            await message.answer("<b>Summary встречи</b>\n\n" + html.escape(summary), disable_web_page_preview=True)
    except Exception:
        if charged:
            await refund_usage(user_id, minutes_to_charge, actions_to_charge)
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
            BotCommand(command="buy", description="Тарифы и оплата"),
            BotCommand(command="balance", description="Мой баланс"),
            BotCommand(command="paysupport", description="Помощь по оплате"),
        ]
    )
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
