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

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = os.getenv("BOT_TOKEN") or "ВСТАВЬ_ТОКЕН_СЮДА"  # или os.getenv для хостинга
ADMIN_ID = int(os.getenv("ADMIN_ID") or 123456789)         # твой ID
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID") or "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"  # ID таблицы

# JSON-ключи сервисного аккаунта (вставь весь JSON как строку)
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS") or """
{
  "type": "service_account",
  "project_id": "your-project",
  "private_key_id": "xxx",
  "private_key": "-----BEGIN PRIVATE KEY-----\\nxxx\\n-----END PRIVATE KEY-----\\n",
  "client_email": "your-service@project.iam.gserviceaccount.com",
  "client_id": "xxx",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "xxx"
}
"""

# =====================================================

# Парсим JSON-ключи
creds_dict = json.loads(GOOGLE_CREDENTIALS)

# Подключение к Google Sheets
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# Создаём листы если нет
try:
    ws_employees = sh.worksheet("Сотрудники")
except gspread.WorksheetNotFound:
    ws_employees = sh.add_worksheet("Сотрудники", rows=100, cols=2)
    ws_employees.append_row(["Имя"])

try:
    ws_criteria = sh.worksheet("Критерии")
except gspread.WorksheetNotFound:
    ws_criteria = sh.add_worksheet("Критерии", rows=100, cols=2)
    ws_criteria.append_row(["Критерий"])

try:
    ws_reviews = sh.worksheet("Отзывы")
except gspread.WorksheetNotFound:
    ws_reviews = sh.add_worksheet("Отзывы", rows=1000, cols=6)
    ws_reviews.append_row(["Время", "Сотрудник", "Критерий", "Оценка", "user_id_скрыт", "Комментарий"])

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

class AdminStates(StatesGroup):
    waiting_employees = State()
    waiting_criteria = State()

# Вспомогательные функции
def get_employees():
    values = ws_employees.col_values(1)[1:]  # без заголовка
    return [(i+1, val.strip()) for i, val in enumerate(values) if val.strip()]

def get_criteria():
    values = ws_criteria.col_values(1)[1:]
    return [(i+1, val.strip()) for i, val in enumerate(values) if val.strip()]

@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        kb = [
            [InlineKeyboardButton(text="Добавить/обновить сотрудников", callback_data="add_employees")],
            [InlineKeyboardButton(text="Добавить/обновить критерии", callback_data="add_criteria")],
            [InlineKeyboardButton(text="Получить ссылку для отзывов", callback_data="get_link")],
            [InlineKeyboardButton(text="Открыть таблицу", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await message.answer("Привет, админ! Выбери действие:", reply_markup=keyboard)
    else:
        employees = get_employees()
        criteria = get_criteria()
        if not employees or not criteria:
            await message.answer("Опрос не настроен. Попроси админа добавить данные.")
            return
        kb = [[InlineKeyboardButton(text=name, callback_data=f"emp_{idx}")] for idx, name in employees]
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await message.answer("Выбери сотрудника для оценки:", reply_markup=keyboard)
        await state.set_state("choose_employee")

# Админ: добавление сотрудников
@router.callback_query(F.data == "add_employees")
async def add_employees(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Пришли список сотрудников (по одному на строку):")
    await state.set_state(AdminStates.waiting_employees)

@router.message(AdminStates.waiting_employees)
async def save_employees(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    names = [n.strip() for n in message.text.split("\n") if n.strip()]
    ws_employees.clear()
    ws_employees.append_row(["Имя"])
    for name in names:
        ws_employees.append_row([name])
    await message.answer(f"Сохранено {len(names)} сотрудников.")
    await state.clear()

# Админ: добавление критериев
@router.callback_query(F.data == "add_criteria")
async def add_criteria(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Пришли критерии (по одному на строку):")
    await state.set_state(AdminStates.waiting_criteria)

@router.message(AdminStates.waiting_criteria)
async def save_criteria(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    crits = [c.strip() for c in message.text.split("\n") if c.strip()]
    ws_criteria.clear()
    ws_criteria.append_row(["Критерий"])
    for crit in crits:
        ws_criteria.append_row([crit])
    await message.answer(f"Сохранено {len(crits)} критериев.")
    await state.clear()

# Админ: ссылка
@router.callback_query(F.data == "get_link")
async def get_link(callback: CallbackQuery):
    username = (await bot.get_me()).username
    link = f"https://t.me/{username}"
    await callback.message.edit_text(f"Ссылка для сотрудников (анонимно): {link}")

# Опрос: выбор сотрудника
@router.callback_query(F.data.startswith("emp_"))
async def choose_employee(callback: CallbackQuery, state: FSMContext):
    emp_idx = int(callback.data.split("_")[1])
    employees = get_employees()
    emp_name = next(name for idx, name in employees if idx == emp_idx)
    await state.update_data(emp_name=emp_name)

    criteria = get_criteria()
    kb = [[InlineKeyboardButton(text=text, callback_data=f"crit_{idx}")] for idx, text in criteria]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    await callback.message.edit_text(f"Оцениваем: {emp_name}\nВыбери критерий:", reply_markup=keyboard)

# Опрос: выбор критерия
@router.callback_query(F.data.startswith("crit_"))
async def choose_criterion(callback: CallbackQuery, state: FSMContext):
    crit_idx = int(callback.data.split("_")[1])
    criteria = get_criteria()
    crit_text = next(text for idx, text in criteria if idx == crit_idx)
    data = await state.get_data()
    emp_name = data["emp_name"]

    kb = [InlineKeyboardButton(text=str(i), callback_data=f"score_{i}_{emp_name}_{crit_text}") for i in range(1, 6)]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[kb])
    await callback.message.edit_text(f"{emp_name} - {crit_text}\nОценка 1-5:", reply_markup=keyboard)

# Опрос: сохранение оценки
@router.callback_query(F.data.startswith("score_"))
async def save_score(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    score = int(parts[1])
    emp_name = parts[2]
    crit_text = "_".join(parts[3:])  # на случай пробелов
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    reviewer_id = f"user_{callback.from_user.id}"  # анонимизируем

    ws_reviews.append_row([timestamp, emp_name, crit_text, score, reviewer_id, ""])

    await callback.message.edit_text("Спасибо! Оценка сохранена анонимно. /start для новой.")
    await state.clear()

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
