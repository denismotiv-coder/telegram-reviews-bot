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

# Переменные из Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

# Google Sheets
creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

ws_emp = sh.worksheet("Сотрудники") if "Сотрудники" in [w.title for w in sh.worksheets()] else sh.add_worksheet("Сотрудники", 100, 2)
ws_crit = sh.worksheet("Критерии") if "Критерии" in [w.title for w in sh.worksheets()] else sh.add_worksheet("Критерии", 100, 2)
ws_rev = sh.worksheet("Отзывы") if "Отзывы" in [w.title for w in sh.worksheets()] else sh.add_worksheet("Отзывы", 1000, 6)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class A(StatesGroup):
    emp = State()
    crit = State()

@router.message(Command("start"))
async def start(m: Message, state: FSMContext):
    if m.from_user.id == ADMIN_ID:
        await m.answer("Админка", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [[InlineKeyboardButton(text="Сотрудники", callback_data="add_emp")]],
            [[InlineKeyboardButton(text="Критерии", callback_data="add_crit")]],
            [[InlineKeyboardButton(text="Ссылка", callback_data="link")]],
            [[InlineKeyboardButton(text="Таблица", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")]]
        ]))
    else:
        names = [row[0] for row in ws_emp.get_all_values()[1:] if row]
        if not names:
            await m.answer("Сотрудников пока нет")
            return
        await m.answer("Кого оцениваем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"e_{i}")] for i, n in enumerate(names, 1)
        ]))

@router.callback_query(F.data == "add_emp")
async def a_emp(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли сотрудников — по одному на строку")
    await state.set_state(A.emp)

@router.message(A.emp)
async def s_emp(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    names = [n.strip() for n in m.text.splitlines() if n.strip()]
    ws_emp.clear()
    ws_emp.append_row(["Имя"])
    ws_emp.append_rows([[n] for n in names])
    await m.answer(f"Добавлено {len(names)} сотрудников")
    await state.clear()

@router.callback_query(F.data == "add_crit")
async def a_crit(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли критерии — по одному на строку")
    await state.set_state(A.crit)

@router.message(A.crit)
async def s_crit(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    crits = [c.strip() for c in m.text.splitlines() if c.strip()]
    ws_crit.clear()
    ws_crit.append_row(["Критерий"])
    ws_crit.append_rows([[c] for c in crits])
    await m.answer(f"Добавлено {len(crits)} критериев")
    await state.clear()

@router.callback_query(F.data == "link")
async def link(c: CallbackQuery):
    u = (await bot.get_me()).username
    await c.message.edit_text(f"https://t.me/{u}")

@router.callback_query(F.data.startswith("e_"))
async def sel_emp(c: CallbackQuery, state: FSMContext):
    i = int(c.data.split("_")[1])
    name = ws_emp.row_values(i)[0]
    await state.update_data(name=name)
    crits = [row[0] for row in ws_crit.get_all_values()[1:] if row]
    await c.message.edit_text(f"Оцениваем: {name}\nКритерий:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=f"c_{j}")] for j, t in enumerate(crits, 1)
    ]))

@router.callback_query(F.data.startswith("c_"))
async def sel_crit(c: CallbackQuery, state: FSMContext):
    i = int(c.data.split("_")[1])
    crit = ws_crit.row_values(i)[0]
    data = await state.get_data()
    await c.message.edit_text(f"{data['name']}\nКритерий: {crit}\nОценка:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{x}⭐", callback_data=f"s_{x}_{data['name']}_{crit}")] for x in range(1,6)
    ]))

@router.callback_query(F.data.startswith("s_"))
async def save_score(c: CallbackQuery, state: FSMContext):
    _, sc, name, crit = c.data.split("_", 3)
    ws_rev.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), name, crit, sc, f"user_{c.from_user.id}", ""])
    await c.message.edit_text("Спасибо! /start — ещё раз")
    await state.clear()

# Запуск, совместимый с Render
async def run_bot():
    dp.include_router(router)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    # Заглушка порта для Render + запуск бота в фоне
    import uvicorn
    from threading import Thread
    Thread(target=lambda: asyncio.run(run_bot()), daemon=True).start()
    uvicorn.run("bot:bot", host="0.0.0.0", port=int(os.getenv("PORT", 10000)), log_level="critical")
