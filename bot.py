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

# Листы с автосозданием
def get_sheet(name, header):
    try:
        return sh.worksheet(name)
    except:
        sheet = sh.add_worksheet(title=name, rows=500, cols=6)
        sheet.append_row(header)
        return sheet

emp = get_sheet("Сотрудники", ["Имя"])
crit = get_sheet("Критерии", ["Критерий"])
rev = get_sheet("Отзывы", ["Время", "Сотрудник", "Критерий", "Оценка", "user_id", "Комментарий"])

# Бот
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class States(StatesGroup):
    adding_emp = State()
    adding_crit = State()

# === АДМИНКА ===
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        names = [row[0] for row in emp.get_all_values()[1:] if row and row[0].strip()]
        if not names:
            await message.answer("Опрос ещё не настроен.")
            return
        await message.answer("Кого оцениваем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"emp_{i}")] for i, name in enumerate(names, 1)
        ]))
        return

    await message.answer("Админ-панель", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сотрудники", callback_data="admin_emp")],
        [InlineKeyboardButton(text="Критерии", callback_data="admin_crit")],
        [InlineKeyboardButton(text="Ссылка для сотрудников", callback_data="get_link")],
        [InlineKeyboardButton(text="Открыть таблицу", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
    ]))

@router.callback_query(F.data == "admin_emp")
async def admin_add_emp(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Пришли список сотрудников — по одному на строку:")
    await state.set_state(States.adding_emp)

@router.message(States.adding_emp)
async def save_employees(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    names = [line.strip() for line in message.text.splitlines() if line.strip()]
    emp.clear()
    emp.append_row(["Имя"])
    emp.append_rows([[name] for name in names])
    await message.answer(f"Добавлено {len(names)} сотрудников")
    await state.clear()

@router.callback_query(F.data == "admin_crit")
async def admin_add_crit(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Пришли критерии — по одному на строку:")
    await state.set_state(States.adding_crit)

@router.message(States.adding_crit)
async def save_criteria(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    criteria = [line.strip() for line in message.text.splitlines() if line.strip()]
    crit.clear()
    crit.append_row(["Критерий"])
    crit.append_rows([[c] for c in criteria])
    await message.answer(f"Добавлено {len(criteria)} критериев")
    await state.clear()

@router.callback_query(F.data == "get_link")
async def send_link(call: CallbackQuery):
    username = (await bot.get_me()).username
    await call.message.edit_text(f"Ссылка для сотрудников:\nhttps://t.me/{username}")

# === ОПРОС ===
@router.callback_query(F.data.startswith("emp_"))
async def select_employee(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split("_")[1])
    name = emp.row_values(idx)[0]
    await state.update_data(employee=name)
    criteria = [row[0] for row in crit.get_all_values()[1:] if row and row[0].strip()]
    await call.message.edit_text(f"Оцениваем: {name}\nВыбери критерий:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=c, callback_data=f"crit_{i}_{name}")] for i, c in enumerate(criteria, 1)
    ]))

@router.callback_query(F.data.startswith("crit_"))
async def select_criterion(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_", 2)
    crit_idx = int(parts[1])
    name = parts[2]
    criterion = crit.row_values(crit_idx)[0]
    await call.message.edit_text(f"{name}\nКритерий: {criterion}\nОценка 1–5:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{i}⭐", callback_data=f"rate_{i}_{name}_{criterion}")] for i in range(1, 6)
    ]))

@router.callback_query(F.data.startswith("rate_"))
async def save_rating(call: CallbackQuery, state: FSMContext):
    _, rating, name, criterion = call.data.split("_", 3)
    rev.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        name,
        criterion,
        rating,
        f"user_{call.from_user.id}",
        ""
    ])
    await call.message.edit_text("Спасибо за оценку!\n/start — оценить ещё")
    await state.clear()

# === ЗАПУСК (работает на Render без ошибок) ===
dp.include_router(router)

if __name__ == "__main__":
    # Запускаем только polling — Render увидит живой процесс и не будет ругаться
    asyncio.run(dp.start_polling(bot))
