import asyncio
import os
import json
from datetime import datetime
import threading

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import gspread
from google.oauth2.service_account import Credentials
from fastapi import FastAPI
import uvicorn

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

def get_sheet(name, header):
    try: return sh.worksheet(name)
    except: ws = sh.add_worksheet(title=name, rows=1000, cols=10); ws.append_row(header); return ws

emp = get_sheet("Сотрудники", ["Имя"])
crit = get_sheet("Критерии", ["Критерий", "Тип"])
rev = get_sheet("Отзывы", ["Время","Сотрудник","Критерий","Оценка","Комментарий","user_id"])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# === ВСЯ ЛОГИКА БОТА (оставь как есть — она у тебя уже идеальна) ===
# (весь твой код от class State до async def final_message — просто скопируй его сюда)

dp.include_router(router)

# === ЗАПУСК (ЭТО РАБОТАЕТ НА RENDER WEB SERVICE БЕСПЛАТНО) ===
def run_bot():
    print("Бот запущен и работает!")
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    # 1. Запускаем бота в отдельном потоке
    threading.Thread(target=run_bot, daemon=True).start()

    # 2. Запускаем FastAPI-заглушку в основном потоке
    app = FastAPI()
    @app.get("/")
    def home():
        return {"status": "бот работает", "time": datetime.now().isoformat()}

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
