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
BOT_TOKEN = os.getenv("8080966853:AAHP1jE9ftGDi8OCpUCviSLfo_BWRFEYdJY
") or "ВСТАВЬ_ТОКЕН_СЮДА"  # или os.getenv для хостинга
ADMIN_ID = int(os.getenv("Motiv33") or 123456789)         # твой ID
SPREADSHEET_ID = os.getenv("1-1PdlrEW5XhDOqMJgym5hBR4QGJsMBwcxDhxf5lSP50") or "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"  # ID таблицы

# JSON-ключи сервисного аккаунта (вставь весь JSON как строку)
GOOGLE_CREDENTIALS = os.getenv("{
  "type": "service_account",
  "project_id": "telegram-bot-reviews",
  "private_key_id": "82f4fa5e7e44b00c29fa27646ba38c95e936f0bb",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDFURF9D1jRX+Ox\njvHyRiBjvDQ9ajJ45kO0P4NhmUBK2krAklxXt/IxHtD3KG2xX7f3VLHQ+WzCcsXM\n4jDwcb30M0EUA/wITB/CA2/4lIqfchCKLGzarqHDrUHI2K1veKLnFY9lUSbUEh9J\nIGwR8CEXf2D/fa4rupyqE+rBFzFfnJ3VScXEfFTfaqj7xYDv4rsdscEJtFX5UnzP\nxkxDjtWnvxR/dirQ5UimtIad3N293ZoX9wMuUTBjCNyCuzTLf/Se3HzK1zPtnXrS\na1PdOa2CVNETueYYCfpdA79GXMSQtODkXzIL9YvwMPgcYIyc3oogr/o7yNNs9KfV\neoGUyqftAgMBAAECggEAAeyryjNP9cwZMlB9FNpT7Wi8rOHaTavMAHrx1SscUv0e\n1e/b36pU+BmK9XLlM4qdNSlUBDScZlYd66IJx0tP+un3Vcbv5igAGWLx+BD1jZ8n\n+xio9wvhCUGpUynqxAqt+EC0YEVlpsIAw50qi5UP7TNnSFAbBSqqlDCKrWjy+jer\nbhMOWYTTAIjpVX0m7yDnrY2moX9F19yGiFw9NTHTf74nOyE358tszQvymLX3MX60\n7/Te2wga/f9A+CNO35cF87ULWAYUvzOe5A24jY/tt8aTMnX/gd5ojHwk2Sxvjb6g\niiZzCr2yx0ifJYwiN5Nw2W63W7K9l2kwDogSmzdP4QKBgQDjdQAxipwBQPDEaMSz\nPNn30NF+ficNubCJTGw0uX/W4LjUr0dNCsEIwjeZiSGbG7wXRsm+IwD5TOpCbcgV\n3WLCn5nGLpF7dtAQzdk8dgYmI4qxUMAVfinlFkQ2oj6eorxjZUcnBK8JqGhnDOPM\nPic81VOSuMhkguOBdByil1dSYQKBgQDeE9DuoGzR9bEdLziYNicIT9R4vC2ZkZPw\nl2w26fSAxmrUihbEiZRgw01F8jyKh4UELRq0HxJY0Ijf68meh44gw+y47novxaKb\nEqAQ77b2QO9vlTRa2CZr9DtvrtzpnBZlPw4ZbLk8EF9rGakZzBtkgEzutsf0z6Gt\nycfyoFAZDQKBgQCufqLQXtrBp3VN6GYGb0d0czFUTildwTeqjQNyC2EEks+Y8oLL\nmtVuB7kpw2cRnFxWqwq4IBhuKNCKd7gI9hb+4fvRawZW5lZGnfTrCkw7VAbhcuZ5\nVpmDUuqv0xYhEw1dX2QPjetOiHDXpa7YkFH/vFRp+fJaEYPBWzdgkKP/4QKBgQCX\nz9IXHoHlceCWw84bd4FtVC06L+G4RmVspgbq7zoewgULsC5qQma1Uy1C8JpkVMog\nlbjYgxkmr7+x21zjy2TkjysHLLdIawGCotPbYBOh+bf0fnng1DxHthjfexk3dWV1\n5wn7ZXCnV8Xy0ALiSL49ENwGn9rHRx0OUY8nFGJNDQKBgQCXzkH1/1gmLvF3Ilvj\nSvELX18c2CbDaLCXW20uaJx9RTKVSwL+p/yRWEUeCs47YHzRte7gq+S88721JGXX\nxSGFtI6F/3sbN8gbaj5rF7UeDSrQ57zyY2doAEcsJrteO9CV2wOMwphkeBfUHBqE\nvYp/1DSpPxszTdcz2XFK0RBYjA==\n-----END PRIVATE KEY-----\n",
  "client_email": "reviews-bot@telegram-bot-reviews.iam.gserviceaccount.com",
  "client_id": "110804900846716095288",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/reviews-bot%40telegram-bot-reviews.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}") or """
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
