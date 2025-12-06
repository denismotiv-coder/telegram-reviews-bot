import asyncio
import os
import json
from datetime import datetime

print("=== ОТЛАДКА НАЧАЛО ===")
print("BOT_TOKEN:", os.getenv("BOT_TOKEN")[:10] + "..." if os.getenv("BOT_TOKEN") else "НЕТ!")
print("ADMIN_ID:", os.getenv("ADMIN_ID"))
print("SPREADSHEET_ID:", os.getenv("SPREADSHEET_ID"))
print("GOOGLE_CREDENTIALS length:", len(os.getenv("GOOGLE_CREDENTIALS", "")))

try:
    creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
    print("JSON распарсился успешно")
    print("client_email:", creds_dict.get("client_email"))
except Exception as e:
    print("ОШИБКА ПАРСИНГА JSON:", str(e))
    raise

from google.oauth2.service_account import Credentials
import gspread

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)

print("Авторизация прошла — пробуем открыть таблицу...")
sh = gc.open_by_key(os.getenv("SPREADSHEET_ID"))
print("ТАБЛИЦА УСПЕШНО ОТКРЫТА! БОТ РАБОТАЕТ!")

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import gspread
from google.oauth2.service_account import Credentials

# Эти переменные берутся из Render (Environment Variables)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")  # весь JSON как строка

# Парсим JSON
creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# Создаём листы
def ensure_sheets():
    for title, header in [("Сотрудники", ["Имя"]), ("Критерии", ["Критерий"]), ("Отзывы", ["Время", "Сотрудник", "Критерий", "Оценка", "user_id", ""])]:
        try: sh.worksheet(title)
        except: ws = sh.add_worksheet(title=title, rows=1000, cols=6); ws.append_row(header)

ensure_sheets()
ws_emp = sh.worksheet("Сотрудники")
ws_crit = sh.worksheet("Критерии")
ws_rev = sh.worksheet("Отзывы")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class A(StatesGroup):
    emp = State(); crit = State()

@router.message(Command("start"))
async def start(m: Message, state: FSMContext):
    if m.from_user.id == ADMIN_ID:
        await m.answer("Админ-панель", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Сотрудники", callback_data="add_emp")],
            [InlineKeyboardButton(text="Критерии", callback_data="add_crit")],
            [InlineKeyboardButton(text="Ссылка", callback_data="link")],
            [InlineKeyboardButton(text="Таблица", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
        ]))
    else:
        kb = [[InlineKeyboardButton(text=n, callback_data=f"e_{i}")] for i, n in enumerate(ws_emp.col_values(1)[1:], 1) if n.strip()]
        await m.answer("Кого оцениваем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("e_"))
async def choose_emp(c: CallbackQuery, state: FSMContext):
    idx = int(c.data.split("_")[1])
    name = ws_emp.col_values(1)[idx]
    await state.update_data(emp=name)
    kb = [[InlineKeyboardButton(text=t, callback_data=f"c_{i}")] for i, t in enumerate(ws_crit.col_values(1)[1:], 1) if t.strip()]
    await c.message.edit_text(f"Оцениваем: {name}\nКритерий:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("c_"))
async def choose_crit(c: CallbackQuery, state: FSMContext):
    idx = int(c.data.split("_")[1])
    crit = ws_crit.col_values(1)[idx]
    data = await state.get_data()
    kb = [[InlineKeyboardButton(text=f"{i}⭐", callback_data=f"s_{i}_{data['emp']}_{crit}")] for i in range(1,2,3,4,5)]
    await c.message.edit_text(f"{data['emp']}\n{crit}\nОценка:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("s_"))
async def save(c: CallbackQuery, state: FSMContext):
    _, score, emp, crit = c.data.split("_", 3)
    ws_rev.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), emp, crit, score, f"user_{c.from_user.id}", ""])
    await c.message.edit_text("Спасибо! /start — ещё раз")
    await state.clear()

# админка
@router.callback_query(F.data == "add_emp")
async def add_e(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли сотрудников по одному на строку:")
    await state.set_state(A.emp)

@router.message(A.emp)
async def save_e(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    names = [n.strip() for n in m.text.split("\n") if n.strip()]
    ws_emp.clear(); ws_emp.append_row(["Имя"]); ws_emp.append_rows([[n] for n in names])
    await m.answer(f"Добавлено {len(names)} сотрудников"); await state.clear()

@router.callback_query(F.data == "add_crit")
async def add_c(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли критерии по одному на строку:")
    await state.set_state(A.crit)

@router.message(A.crit)
async def save_c(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    crits = [c.strip() for c in m.text.split("\n") if c.strip()]
    ws_crit.clear(); ws_crit.append_row(["Критерий"]); ws_crit.append_rows([[c] for c in crits])
    await m.answer(f"Добавлено {len(crits)} критериев"); await state.clear()

@router.callback_query(F.data == "link")
async def link(c: CallbackQuery):
    username = (await bot.get_me()).username
    await c.message.edit_text(f"Ссылка для сотрудников:\nhttps://t.me/{username}")

async def main():
    dp.include_router(router)
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

# Для Render — заглушка HTTP-сервера
import uvicorn
if __name__ == "__main__":
    uvicorn.run("bot:dp", host="0.0.0.0", port=int(os.getenv("PORT", 10000)), log_level="error")
