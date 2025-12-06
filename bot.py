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

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # твой ID — 323601296
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# Листы
def sheet(name, header):
    try: return sh.worksheet(name)
    except: s = sh.add_worksheet(title=name, rows=500, cols=6); s.append_row(header); return s

emp = sheet("Сотрудники", ["Имя"])
crit = sheet("Критерии", ["Критерий"])
rev = sheet("Отзывы", ["Время","Сотрудник","Критерий","Оценка","user_id",""])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class S(StatesGroup):
    emp = State()
    crit = State()

# === ОСНОВНОЕ МЕНЮ АДМИНА ===
async def admin_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сотрудники", callback_data="add_emp")],
        [InlineKeyboardButton(text="Критерии", callback_data="add_crit")],
        [InlineKeyboardButton(text="Ссылка для сотрудников", callback_data="link")],
        [InlineKeyboardButton(text="Таблица результатов", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
    ])
    await message.answer("Админ-панель", reply_markup=kb)

# === КОМАНДЫ ===
@router.message(Command("start"))
async def start(m: Message, state: FSMContext):
    await state.clear()
    if m.from_user.id == ADMIN_ID:
        await admin_menu(m)
    else:
        names = [r[0] for r in emp.get_all_values()[1:] if r and r[0].strip()]
        if not names:
            await m.answer("Опрос ещё не настроен")
            return
        await m.answer("Кого оцениваем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"e_{i}")] for i,n in enumerate(names,1)
        ]))

# Любой текст от админа — возвращаем в меню
@router.message()
async def any_text(m: Message, state: FSMContext):
    if m.from_user.id == ADMIN_ID:
        await state.clear()
        await admin_menu(m)

# === АДМИНКА ===
@router.callback_query(F.data == "add_emp")
async def add_emp(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли сотрудников — по одному на строку:")
    await state.set_state(S.emp)

@router.message(S.emp)
async def save_emp(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    names = [n.strip() for n in m.text.splitlines() if n.strip()]
    emp.clear(); emp.append_row(["Имя"]); emp.append_rows([[n] for n in names])
    await m.answer(f"Добавлено {len(names)} сотрудников")
    await admin_menu(m)
    await state.clear()

@router.callback_query(F.data == "add_crit")
async def add_crit(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли критерии — по одному на строку:")
    await state.set_state(S.crit)

@router.message(S.crit)
async def save_crit(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    items = [n.strip() for n in m.text.splitlines() if n.strip()]
    crit.clear(); crit.append_row(["Критерий"]); crit.append_rows([[n] for n in items])
    await m.answer(f"Добавлено {len(items)} критериев")
    await admin_menu(m)
    await state.clear()

@router.callback_query(F.data == "link")
async def link(c: CallbackQuery):
    u = (await bot.get_me()).username
    await c.message.edit_text(f"Ссылка для сотрудников:\nhttps://t.me/{u}")
    await asyncio.sleep(3)
    await admin_menu(c.message)

# === ОПРОС ===
@router.callback_query(F.data.startswith("e_"))
async def sel_emp(c: CallbackQuery, state: FSMContext):
    i = int(c.data.split("_")[1])
    name = emp.row_values(i)[0]
    await state.update_data(name=name)
    items = [r[0] for r in crit.get_all_values()[1:] if r and r[0].strip()]
    await c.message.edit_text(f"Оцениваем: {name}\nКритерий:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=f"c_{j}")] for j,t in enumerate(items,1)
    ]))

@router.callback_query(F.data.startswith("c_"))
async def sel_crit(c: CallbackQuery, state: FSMContext):
    i = int(c.data.split("_")[1])
    criterion = crit.row_values(i)[0]
    data = await state.get_data()
    await c.message.edit_text(f"{data['name']}\nКритерий: {criterion}\nОценка 1–5:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{x}⭐", callback_data=f"r_{x}_{data['name']}_{criterion}")] for x in range(1,6)
    ]))

@router.callback_query(F.data.startswith("r_"))
async def save_rate(c: CallbackQuery, state: FSMContext):
    _, score, name, criterion = c.data.split("_", 3)
    rev.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), name, criterion, score, f"user_{c.from_user.id}", ""])
    await c.message.edit_text("Спасибо за оценку!")
    await asyncio.sleep(2)
    await start(c.message, state)  # возвращаем в начало (для обычных пользователей)

# === ЗАПУСК (Render-friendly) ===
dp.include_router(router)

if __name__ == "__main__":
    # Просто запускаем polling — Render держит процесс живым
    asyncio.run(dp.start_polling(bot))
