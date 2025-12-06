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

# Листы
def ws(name):
    try:
        return sh.worksheet(name)
    except:
        w = sh.add_worksheet(title=name, rows=500, cols=5)
        w.append_row(["Заголовок"])
        return w

emp = ws("Сотрудники")
crit = ws("Критерии")
rev = ws("Отзывы")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class S(StatesGroup):
    add_emp = State()
    add_crit = State()

# === АДМИН ===
@router.message(Command("start"))
async def start(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        names = [r[0] for r in emp.get_all_values()[1:] if r]
        if not names:
            await m.answer("Опрос ещё не настроен")
            return
        await m.answer("Кого оцениваем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=n, callback_data=f"e_{i}")] for i, n in enumerate(names, 1)
        ]))
        return

    await m.answer("Админка", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [[InlineKeyboardButton(text="Сотрудники", callback_data="ae")]],
        [[InlineKeyboardButton(text="Критерии", callback_data="ac")]],
        [[InlineKeyboardButton(text="Ссылка", callback_data="link")]],
        [[InlineKeyboardButton(text="Таблица", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")]]
    ]))

@router.callback_query(F.data == "ae")
async def ae(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли сотрудников — по одному на строку")
    await state.set_state(S.add_emp)

@router.message(S.add_emp)
async def se(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    n = [x.strip() for x in m.text.splitlines() if x.strip()]
    emp.clear(); emp.append_row(["Имя"]); emp.append_rows([[x] for x in n])
    await m.answer(f"Добавлено {len(n)} сотрудников")
    await state.clear()

@router.callback_query(F.data == "ac")
async def ac(c: CallbackQuery, state: FSMContext):
    await c.message.edit_text("Пришли критерии — по одному на строку")
    await state.set_state(S.add_crit)

@router.message(S.add_crit)
async def sc(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    c = [x.strip() for x in m.text.splitlines() if x.strip()]
    crit.clear(); crit.append_row(["Критерий"]); crit.append_rows([[x] for x in c])
    await m.answer(f"Добавлено {len(c)} критериев")
    await state.clear()

@router.callback_query(F.data == "link")
async def link(c: CallbackQuery):
    u = (await bot.get_me()).username
    await c.message.edit_text(f"https://t.me/{u}")

# === ОПРОС ===
@router.callback_query(F.data.startswith("e_"))
async def e(c: CallbackQuery, state: FSMContext):
    i = int(c.data.split("_")[1])
    name = emp.row_values(i)[0]
    await state.update_data(name=name)
    kb = [[InlineKeyboardButton(text=t, callback_data=f"c_{j}")] for j, t in enumerate([r[0] for r in crit.get_all_values()[1:] if r], 1)]
    await c.message.edit_text(f"Оцениваем: {name}\nКритерий:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("c_"))
async def c_(c: CallbackQuery, state: FSMContext):
    i = int(c.data.split("_")[1])
    cr = crit.row_values(i)[0]
    d = await state.get_data()
    kb = [[InlineKeyboardButton(text=f"{x}⭐", callback_data=f"s_{x}_{d['name']}_{cr}")] for x in range(1,6)]
    await c.message.edit_text(f"{d['name']}\nКритерий: {cr}\nОценка:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("s_"))
async def s(c: CallbackQuery, state: FSMContext):
    _, score, name, cr = c.data.split("_", 3)
    rev.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), name, cr, score, f"user_{c.from_user.id}", ""])
    await c.message.edit_text("Спасибо! /start — ещё")
    await state.clear()

# === ЗАПУСК ДЛЯ RENDER ===
dp.include_router(router)

async def polling():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    # Заглушка порта + бот в фоне
    from threading import Thread
    Thread(target=lambda: asyncio.run(polling()), daemon=True).start()
    
    # Минимальный веб-сервер только для Render
    from fastapi import FastAPI
    app = FastAPI()
    @app.get("/")
    async def root():
        return {"status": "бот работает"}
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
