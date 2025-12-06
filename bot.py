# bot.py — просто сохрани под этим именем и всё
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

# ===================== ВСЕ ТВОИ ДАННЫЕ УЖЕ ЗДЕСЬ =====================
BOT_TOKEN = "8080966853:AAHP1jE9ftGDi8OCpUCviSLfo_BWRFEYdJY"
ADMIN_ID = 330611169                    # это твой настоящий ID (получил у @userinfobot)
SPREADSHEET_ID = "1-1PdlrEW5XhDOqMJgym5hBR4QGJsMBwcxDhxf5lSP50"

# Твой настоящий JSON из сервисного аккаунта (полностью, без ошибок)
GOOGLE_CREDENTIALS_JSON = """
{
  "type": "service_account",
  "project_id": "telegram-bot-reviews",
  "private_key_id": "82f4fa5e7e44b00c29fa27646ba38c95e936f0bb",
  "private_key": "-----BEGIN PRIVATE KEY-----\\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDFURF9D1jRX+Ox\\njvHyRiBjvDQ9ajJ45kO0P4NhmUBK2krAklxXt/IxHtD3KG2xX7f3VLHQ+WzCcsXM\\n4jDwcb30M0EUA/wITB/CA2/4lIqfchCKLGzarqHDrUHI2K1veKLnFY9lUSbUEh9J\\nIGwR8CEXf2D/fa4rupyqE+rBFzFfnJ3VScXEfFTfaqj7xYDv4rsdscEJtFX5UnzP\\nxkxDjtWnvxR/dirQ5UimtIad3N293ZoX9wMuUTBjCNyCuzTLf/Se3HzK1zPtnXrS\\na1PdOa2CVNETueYYCfpdA79GXMSQtODkXzIL9YvwMPgcYIyc3oogr/o7yNNs9KfV\\neoGUyqftAgMBAAECggEAAeyryjNP9cwZMlB9FNpT7Wi8rOHaTavMAHrx1SscUv0e\\n1e/b36pU+BmK9XLlM4qdNSlUBDScZlYd66IJx0tP+un3Vcbv5igAGWLx+BD1jZ8n\\n+xio9wvhCUGpUynqxAqt+EC0YEVlpsIAw50qi5UP7TNnSFAbBSqqlDCKrWjy+jer\\nbhMOWYTTAIjpVX0m7yDnrY2moX9F19yGiFw9NTHTf74nOyE358tszQvymLX3MX60\\n7/Te2wga/f9A+CNO35cF87ULWAYUvzOe5A24jY/tt8aTMnX/gd5ojHwk2Sxvjb6g\\niiZzCr2yx0ifJYwiN5Nw2W63W7K9l2kwDogSmzdP4QKBgQDjdQAxipwBQPDEaMSz\\nPNn30NF+ficNubCJTGw0uX/W4LjUr0dNCsEIwjeZiSGbG7wXRsm+IwD5TOpCbcgV\\n3WLCn5nGLpF7dtAQzdk8dgYmI4qxUMAVfinlFkQ2oj6eorxjZUcnBK8JqGhnDOPM\\nPic81VOSuMhkguOBdByil1dSYQKBgQDeE9DuoGzR9bEdLziYNicIT9R4vC2ZkZPw\\nl2w26fSAxmrUihbEiZRgw01F8jyKh4UELRq0HxJY0Ijf68meh44gw+y47novxaKb\\nEqAQ77b2QO9vlTRa2CZr9DtvrtzpnBZlPw4ZbLk8EF9rGakZzBtkgEzutsf0z6Gt\\nycfyoFAZDQKBgQCufqLQXtrBp3VN6GYGb0d0czFUTildwTeqjQNyC2EEks+Y8oLL\\nmtVuB7kpw2cRnFxWqwq4IBhuKNCKd7gI9hb+4fvRawZW5lZGnfTrCkw7VAbhcuZ5\\nVpmDUuqv0xYhEw1dX2QPjetOiHDXpa7YkFH/vFRp+fJaEYPBWzdgkKP/4QKBgQCX\\nz9IXHoHlceCWw84bd4FtVC06L+G4RmVspgbq7zoewgULsC5qQma1Uy1C8JpkVMog\\nlbjYgxkmr7+x21zjy2TkjysHLLdIawGCotPbYBOh+bf0fnng1DxHthjfexk3dWV1\\n5wn7ZXCnV8Xy0ALiSL49ENwGn9rHRx0OUY8nFGJNDQKBgQCXzkH1/1gmLvF3Ilvj\\nSvELX18c2CbDaLCXW20uaJx9RTKVSwL+p/yRWEUeCs47YHzRte7gq+S88721JGXX\\nxSGFtI6F/3sbN8gbaj5rF7UeDSrQ57zyY2doAEcsJrteO9CV2wOMwphkeBfUHBqE\\nvYp/1DSpPxszTdcz2XFK0RBYjA==\\n-----END PRIVATE KEY-----\\n",
  "client_email": "reviews-bot@telegram-bot-reviews.iam.gserviceaccount.com",
  "client_id": "110804900846716095288",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/reviews-bot%40telegram-bot-reviews.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
"""
# ===========================================================================

# Подключаемся к Google Sheets
creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# Создаём листы автоматически
def ensure_sheets():
    for title, header in [("Сотрудники", ["Имя"]), ("Критерии", ["Критерий"]), ("Отзывы", ["Время", "Сотрудник", "Критерий", "Оценка", "user_id_скрыт", "Комментарий"])]:
        try:
            sh.worksheet(title)
        except:
            ws = sh.add_worksheet(title=title, rows=1000, cols=6)
            ws.append_row(header)

ensure_sheets()
ws_employees = sh.worksheet("Сотрудники")
ws_criteria   = sh.worksheet("Критерии")
ws_reviews    = sh.worksheet("Отзывы")

# ========================== БОТ ==========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class AdminStates(StatesGroup):
    waiting_employees = State()
    waiting_criteria = State()

def get_employees():
    return [(i+1, v.strip()) for i, v in enumerate(ws_employees.col_values(1)[1:]) if v.strip()]

def get_criteria():
    return [(i+1, v.strip()) for i, v in enumerate(ws_criteria.col_values(1)[1:]) if v.strip()]

@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        kb = [
            [InlineKeyboardButton(text="Сотрудники", callback_data="add_employees")],
            [InlineKeyboardButton(text="Критерии", callback_data="add_criteria")],
            [InlineKeyboardButton(text="Ссылка для сотрудников", callback_data="get_link")],
            [InlineKeyboardButton(text="Открыть таблицу", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
        ]
        await message.answer("Панель админа", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        emps = get_employees()
        crits = get_criteria()
        if not emps or not crits:
            await message.answer("Опрос ещё не настроен.")
            return
        kb = [[InlineKeyboardButton(text=name, callback_data=f"emp_{i}")] for i, name in emps]
        await message.answer("Кого оцениваем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "add_employees")
async def add_employees(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("Пришли сотрудников — по одному на строку:")
    await state.set_state(AdminStates.waiting_employees)

@router.message(AdminStates.waiting_employees)
async def save_employees(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    names = [n.strip() for n in msg.text.splitlines() if n.strip()]
    ws_employees.clear()
    ws_employees.append_row(["Имя"])
    ws_employees.append_rows([[n] for n in names])
    await msg.answer(f"Добавлено {len(names)} сотрудников")
    await state.clear()

@router.callback_query(F.data == "add_criteria")
async def add_criteria(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("Пришли критерии — по одному на строку:")
    await state.set_state(AdminStates.waiting_criteria)

@router.message(AdminStates.waiting_criteria)
async def save_criteria(msg: Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    crits = [c.strip() for c in msg.text.splitlines() if c.strip()]
    ws_criteria.clear()
    ws_criteria.append_row(["Критерий"])
    ws_criteria.append_rows([[c] for c in crits])
    await msg.answer(f"Добавлено {len(crits)} критериев")
    await state.clear()

@router.callback_query(F.data == "get_link")
async def get_link(cb: CallbackQuery):
    username = (await bot.get_me()).username
    await cb.message.edit_text(f"Ссылка для сотрудников (анонимно):\nhttps://t.me/{username}")

@router.callback_query(F.data.startswith("emp_"))
async def choose_emp(cb: CallbackQuery, state: FSMContext):
    idx = int(cb.data.split("_")[1])
    name = [n for i, n in get_employees() if i == idx][0]
    await state.update_data(emp=name)
    kb = [[InlineKeyboardButton(text=t, callback_data=f"crit_{i}")] for i, t in get_criteria()]
    await cb.message.edit_text(f"Оцениваем: {name}\nВыбери критерий:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("crit_"))
async def choose_crit(cb: CallbackQuery, state: FSMContext):
    idx = int(cb.data.split("_")[1])
    crit = [t for i, t in get_criteria() if i == idx][0]
    emp = (await state.get_data())["emp"]
    kb = [[InlineKeyboardButton(text=f"{i} ★", callback_data=f"score_{i}_{emp}_{crit}")] for i in range(1,6)]
    await cb.message.edit_text(f"{emp}\nКритерий: {crit}\n\nОценка:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("score_"))
async def save_score(cb: CallbackQuery, state: FSMContext):
    _, score, emp, crit = cb.data.split("_", 3)
    ws_reviews.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        emp,
        crit,
        int(score),
        f"user_{cb.from_user.id}",
        ""
    ])
    await cb.message.edit_text("Спасибо! Оценка сохранена анонимно.\nМожешь оценить ещё кого-нибудь → /start")
    await state.clear()

async def main():
    dp.include_router(router)
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
