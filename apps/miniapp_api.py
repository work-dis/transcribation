import hashlib
import hmac
import json
import os
import sqlite3
import time
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = os.environ.get("TRANSCRIBER_DB_PATH", "/data/voicetype.db")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
app = FastAPI(title="VoiceType Mini App API")
app.add_middleware(CORSMiddleware, allow_origins=[os.environ.get("MINI_APP_ORIGIN", "*")], allow_methods=["GET"], allow_headers=["Authorization"])

def user_id_from_init_data(authorization: str | None) -> int:
    if not authorization or not authorization.startswith("tma ") or not BOT_TOKEN:
        raise HTTPException(401, "Telegram authorization required")
    pairs = dict(parse_qsl(authorization[4:], keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as exc:
        raise HTTPException(401, "Invalid authorization") from exc
    if not received_hash or time.time() - auth_date > 86400:
        raise HTTPException(401, "Expired authorization")
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise HTTPException(401, "Invalid authorization")
    user_id = int(json.loads(pairs.get("user", "{}"))["id"])
    return user_id

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/v1/miniapp/records")
def records(authorization: str | None = Header(default=None)):
    user_id = user_id_from_init_data(authorization)
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute("SELECT id, created_at, text, summary FROM transcriptions WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 20", (user_id,)).fetchall()
    return [{"id": str(item[0]), "title": "Расшифровка", "date": item[1], "duration": "", "preview": item[2].replace("\n", " ")[:180], "text": item[2], "summary": item[3] or ""} for item in rows]

@app.get("/v1/miniapp/balance")
def balance(authorization: str | None = Header(default=None)):
    user_id = user_id_from_init_data(authorization)
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT minutes, ai_actions FROM balances WHERE user_id = ?", (user_id,)).fetchone()
    return {"minutes": int(row[0]) if row else 0, "ai_actions": int(row[1]) if row else 0}
