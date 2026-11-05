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
                language TEXT NOT NULL DEFAULT 'ru',
                mode TEXT NOT NULL DEFAULT 'quick'
            );
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS balances (
                user_id INTEGER PRIMARY KEY,
                minutes INTEGER NOT NULL DEFAULT 0,
                ai_actions INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_code TEXT NOT NULL,
                charge_id TEXT NOT NULL UNIQUE,
                stars INTEGER NOT NULL,
                minutes INTEGER NOT NULL,
                ai_actions INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_transcriptions_user
                ON transcriptions(user_id, created_at DESC);
            """
        )
        cursor = await db.execute("PRAGMA table_info(user_settings)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "mode" not in columns:
            await db.execute("ALTER TABLE user_settings ADD COLUMN mode TEXT NOT NULL DEFAULT 'quick'")
        cursor = await db.execute("PRAGMA table_info(transcriptions)")
        transcription_columns = {row[1] for row in await cursor.fetchall()}
        if "summary" not in transcription_columns:
            await db.execute("ALTER TABLE transcriptions ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
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


async def get_mode(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT mode FROM user_settings WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
    return row[0] if row and row[0] in {"quick", "conference", "summary"} else "quick"


async def set_mode(user_id: int, mode: str) -> None:
    if mode not in {"quick", "conference", "summary"}:
        mode = "quick"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_settings(user_id, mode) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET mode = excluded.mode",
            (user_id, mode),
        )
        await db.commit()


async def save_transcription(user_id: int, chat_id: int, text: str, summary: str = "") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO transcriptions(user_id, chat_id, text, summary) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, text, summary),
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


async def recent_transcriptions(user_id: int, limit: int = 5) -> list[tuple[str, str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT created_at, text, summary FROM transcriptions WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
        return await cursor.fetchall()


async def get_balance(user_id: int) -> tuple[int, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT minutes, ai_actions FROM balances WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
    return (int(row[0]), int(row[1])) if row else (0, 0)


async def charge_minutes(user_id: int, minutes: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE balances SET minutes = minutes - ? WHERE user_id = ? AND minutes >= ?",
            (minutes, user_id, minutes),
        )
        await db.commit()
        return cursor.rowcount == 1


async def charge_usage(user_id: int, minutes: int, ai_actions: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE balances SET minutes = minutes - ?, ai_actions = ai_actions - ? "
            "WHERE user_id = ? AND minutes >= ? AND ai_actions >= ?",
            (minutes, ai_actions, user_id, minutes, ai_actions),
        )
        await db.commit()
        return cursor.rowcount == 1


async def refund_minutes(user_id: int, minutes: int) -> None:
    await add_balance(user_id, minutes, 0)


async def refund_usage(user_id: int, minutes: int, ai_actions: int) -> None:
    await add_balance(user_id, minutes, ai_actions)


async def add_balance(user_id: int, minutes: int, ai_actions: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO balances(user_id, minutes, ai_actions) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET minutes = minutes + excluded.minutes, "
            "ai_actions = ai_actions + excluded.ai_actions",
            (user_id, minutes, ai_actions),
        )
        await db.commit()


async def record_payment(
    user_id: int, plan_code: str, charge_id: str, stars: int, minutes: int, ai_actions: int
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO payments(user_id, plan_code, charge_id, stars, minutes, ai_actions) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, plan_code, charge_id, stars, minutes, ai_actions),
            )
            await db.execute(
                "INSERT INTO balances(user_id, minutes, ai_actions) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET minutes = minutes + excluded.minutes, "
                "ai_actions = ai_actions + excluded.ai_actions",
                (user_id, minutes, ai_actions),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            await db.rollback()
            return False
