from __future__ import annotations

import os
from pathlib import Path

import aiosqlite

DB_PATH = os.environ.get("TRANSCRIBER_DB_PATH", "/data/voicetype.db")


async def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'ru'
            );
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_transcriptions_user
                ON transcriptions(user_id, created_at DESC);
            """
        )
        await db.commit()


async def get_language(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT language FROM user_settings WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
    return row[0] if row else "ru"


async def set_language(user_id: int, language: str) -> None:
    if language not in {"ru", "auto"}:
        language = "ru"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_settings(user_id, language) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET language = excluded.language",
            (user_id, language),
        )
        await db.commit()


async def save_transcription(user_id: int, chat_id: int, text: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO transcriptions(user_id, chat_id, text) VALUES (?, ?, ?)",
            (user_id, chat_id, text),
        )
        cursor = await db.execute(
            "SELECT id FROM transcriptions WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT -1 OFFSET 20",
            (user_id,),
        )
        old_rows = await cursor.fetchall()
        if old_rows:
            await db.executemany("DELETE FROM transcriptions WHERE id = ?", old_rows)
        await db.commit()


async def recent_transcriptions(user_id: int, limit: int = 5) -> list[tuple[str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT created_at, text FROM transcriptions WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
        return await cursor.fetchall()
