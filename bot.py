import asyncio
import os
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import gspread
from google.oauth2.service_account import Credentials

# === ПЕРЕМЕННЫЕ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# Листы
def get_ws(name):
    try: return sh.worksheet(name)
    except: ws = sh.add_worksheet(title=name, rows=1000, cols=6); ws.append_row(["Заголовок"]); return ws

ws_emp = get_ws("Сотрудники")
ws_crit = get_ws("Критерии")
ws_rev = get_ws("Отзывы")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class State(StatesGroup):
    employees = State()
    criteria = State()

# === АДМИНКА ===
@router.message(Command("start"))
async def start(m: Message, state: FSMContext):
    if m.from_user.id == ADMIN_ID:
        kb = [[InlineKeyboardButton(text=t, callback_data=c)] for t,c in [
            ("Сотрудники", "add_emp"), ("Критерии", "add_crit"),
            ("Ссылка для сотрудников", "link"), ("Таблица", f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")]]
        await m.answer("Админка", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        names = [r[0] for r in ws_emp.get_all_values()[1:] if r]
        if not names:
            await m.answer("Сотрудников ещё нет")
            return
        kb = [[InlineKeyboardButton(text=n, callback_data=f"e_{i}")] for i,n in enumerate(names,1)]
        await m.answer("Кого оцениваем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "add_emp")
async def add_emp(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли сотрудников — по одному на строку")
    await state.set_state(State.employees)

@router.message(State.employees)
async def save_emp(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    names = [n.strip() for n in m.text.splitlines() if n.strip()]
    ws_emp.clear()
    ws_emp.append_row(["Имя"])
    ws_emp.append_rows([[n] for n in names])
    await m.answer(f"Добавлено {len(names)} сотрудников")
    await state.clear()

@router.callback_query(F.data == "add_crit")
async def add_crit(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли критерии — по одному на строку")
    await state.set_state(State.criteria)

@router.message(State.criteria)
async def save_crit(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    crits = [c.strip() for c in m.text.splitlines() if c.strip()]
    ws_crit.clear()
    ws_crit.append_row(["Критерий"])
    ws_crit.append_rows([[c] for c in crits])
    await m.answer(f"Добавлено {len(crits)} критериев")
    await state.clear()

@router.callback_query(F.data == "link")
async def link(c: CallbackQuery):
    username = (await bot.get_me()).username
    await c.message.edit_text(f"https://t.me/{username}")

# === ОПРОС ===
@router.callback_query(F.data.startswith("e_"))
async def emp(c: CallbackQuery, state: FSMContext):
    name = ws_emp.row_values(int(c.data.split("_")[1]))[0]
    await state.update_data(emp=name)
    crits = [r[0] for r in ws_crit.get_all_values()[1:] if r]
    kb = [[InlineKeyboardButton(text=t, callback_data=f"c_{i}")] for i,t in enumerate(crits,1)]
    await c.message.edit_text(f"Оцениваем: {name}\nКритерий:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("c_"))
async def crit(c: CallbackQuery, state: FSMContext):
    crit = ws_crit.row_values(int(c.data.split("_")[1]))[0]
    data = await state.get_data()
    kb = [[InlineKeyboardButton(text=f"{i}⭐", callback_data=f"s_{i}_{data['emp']}_{crit}")] for i in range(1,6)]
    await c.message.edit_text(f"{data['emp']}\nКритерий: {crit}\nОценка:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("s_"))
async def score(c: CallbackQuery, state: FSMContext):
    _, sc, emp, crit = c.data.split("_", 3)
    ws_rev.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), emp, crit, sc, f"user_{c.from_user.id}", ""])
    await c.message.edit_text("Спасибо! /start — ещё")
    await state.clear()

# === ЗАПУСК ===
async def main():
    dp.include_router(router)
    # Заглушка для Render — чтобы не ругался на порт
    import uvicorn
    import threading
    def run_bot():
        asyncio.run(dp.start_polling(bot, skip_updates=True))
    threading.Thread(target=run_bot, daemon=True).start()
    uvicorn.run("bot:bot", host="0.0.0.0", port=int(os.getenv("PORT", 10000)), log_level="critical")

if __name__ == "__main__":
    main()
