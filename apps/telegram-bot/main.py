"""Telegram Bot API adapter."""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from conversation_core.config import settings
async def main():
    if not settings.telegram_bot_token: raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    bot=Bot(settings.telegram_bot_token); dp=Dispatcher()
    @dp.message(Command(commands=["start", "help"]))
    async def start(message): await message.answer("Отправь голосовое, аудио или видео — я сделаю транскрипцию и анализ.")
    await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
