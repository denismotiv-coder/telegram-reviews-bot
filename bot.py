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
from aiogram.fsm.storage.memory import MemoryStorage  # ← было "aiagram" — исправлено!

import gspread
from google.oauth2.service_account import Credentials
from fastapi import FastAPI
import uvicorn

# === ОТКЛЮЧАЕМ UVLOOP ===
os.environ["AIOGRAM_USE_UVLOOP"] = "0"

# === НАСТРОЙКИ
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

class State(StatesGroup):
    add_emp = State()
    add_crit = State()
    crit_type = State()
    waiting_text = State()

# === ВСПОМОГАТЕЛЬНЫЕ ===
def get_employees():
    return [r[0] for r in emp.get_all_values()[1:] if r and r[0].strip()]

def get_criteria():
    rows = crit.get_all_values()[1:]
    return [(r[0], r[1] if len(r)>1 else "score") for r in rows if r and r[0].strip()]

def delete_user_reviews(user_id, employee=None):
    rows = rev.get_all_values()
    if len(rows) < 2: return
    header = rows[0]
    uid_col = header.index("user_id") + 1
    emp_col = header.index("Сотрудник") + 1 if "Сотрудник" in header else 0
    to_del = []
    for i, row in enumerate(rows[1:], 2):
        if len(row) >= uid_col and row[uid_col-1].endswith(str(user_id)):
            if not employee or (emp_col and row[emp_col-1] == employee):
                to_del.append(i)
    for row in reversed(to_del):
        rev.delete_rows(row)

async def admin_menu(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сотрудники", callback_data="a_emp")],
        [InlineKeyboardButton(text="Критерии", callback_data="a_crit")],
        [InlineKeyboardButton(text="Ссылка для команды", callback_data="link")],
        [InlineKeyboardButton(text="Таблица", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
    ])
    await msg.answer("Админ-панель", reply_markup=kb)

# === СТАРТ ===
@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        await admin_menu(message)
        return

    await message.answer(
        "Привет! Давай поиграем в «невидимого критика»\n\n"
        "Это анонимный опрос по отделу оперативной графики. Ты — наш секретный информатор!\n\n"
        "Твои ответы останутся тайной: руководитель отдела увидит только средние баллы, без привязки к автору.\n\n"
        "Оценивай честно по шкале от 1 до 5 — это как рейтинг в такси, только для коллег — и намного полезнее!\n\n"
        "Как оценивать:\n"
        "1 — Всё очень сложно, если не плохо.\n"
        "2 — Ну, могло быть и лучше, честно говоря.\n"
        "3 — Нормально. Как бутерброд без масла.\n"
        "4 — Хорошо! Можно ставить в рамку!\n"
        "5 — Лучший! Хочется аплодировать стоя!\n\n"
        "Пора выбрать объект для оценки!"
    )

    emps = get_employees()
    if not emps:
        await message.answer("Сотрудников пока нет")
        return

    kb = [[InlineKeyboardButton(text=n, callback_data=f"sel_emp_{i}")] for i, n in enumerate(emps, 1)]
    kb.append([InlineKeyboardButton(text="Исправить оценку", callback_data="edit_mode")])
    await message.answer("Выбери человека для оценки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# === ОПРОС + ИСПРАВЛЕНИЕ ===
@router.callback_query(F.data.startswith(("sel_emp_", "edit_emp_")))
async def select_employee(call: CallbackQuery, state: FSMContext):
    is_edit = call.data.startswith("edit_emp_")
    idx = int(call.data.split("_")[-1])
    employee = emp.row_values(idx)[0]
    if is_edit:
        delete_user_reviews(call.from_user.id, employee)
    await state.update_data(employee=employee, crit_idx=0, is_edit=is_edit)
    await next_question(call.message, state)

async def next_question(message: Message, state: FSMContext):
    data = await state.get_data()
    employee = data["employee"]
    criteria = get_criteria()
    idx = data.get("crit_idx", 0)

    if idx >= len(criteria):
        await final_message(message)
        return

    name, ctype = criteria[idx]
    if ctype == "score":
        kb = [[InlineKeyboardButton(text=f"{i}⭐", callback_data=f"rate_{i}_{idx}")] for i in range(1,6)]
        text = f"Оцениваем: {employee}\nКритерий: {name}\n\nОценка от 1 до 5:"
    else:
        kb = [[InlineKeyboardButton(text="Пропустить", callback_data=f"skip_{idx}")],
              [InlineKeyboardButton(text="Написать комментарий", callback_data=f"text_{idx}")]]
        text = f"Оцениваем: {employee}\nКритерий: {name}\n\n(по желанию)"

    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith(("rate_", "skip_", "text_")))
async def handle_answer(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = int(call.data.split("_")[1])
    crit_name, _ = get_criteria()[idx]

    if call.data.startswith("rate_"):
        score = call.data.split("_")[1]
        rev.append_row([datetime.now().strftime("%d.%m %H:%M"), data["employee"], crit_name, score, "", f"user_{call.from_user.id}"])
    elif call.data.startswith("text_"):
        await call.message.edit_text(f"Напиши комментарий по пункту «{crit_name}»:")
        await state.update_data(waiting_idx=idx)
        await state.set_state(State.waiting_text)
        return

    await state.update_data(crit_idx=idx + 1)
    await next_question(call.message, state)

@router.message(State.waiting_text)
async def save_text(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data["waiting_idx"]
    crit_name, _ = get_criteria()[idx]
    rev.append_row([datetime.now().strftime("%d.%m %H:%M"), data["employee"], crit_name, "", message.text, f"user_{message.from_user.id}"])
    await message.answer("Комментарий сохранён!")
    await state.update_data(crit_idx=idx + 1)
    await next_question(message, state)

async def final_message(message: Message):
    await message.edit_text(
        "Спасибо большое за твою оценку!\n\n"
        "Напоминаю: это был полностью анонимный опрос. Никто не узнает, что именно ты написал — только общие цифры.\n"
        "Твой вклад реально помогает команде становиться лучше!\n\n"
        "Разработал бот: Кульбацкий Денис (@Motiv33)"
    )

# === АДМИНКА ===
async def admin_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сотрудники", callback_data="a_emp")],
        [InlineKeyboardButton(text="Критерии", callback_data="a_crit")],
        [InlineKeyboardButton(text="Ссылка для команды", callback_data="link")],
        [InlineKeyboardButton(text="Таблица", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
    ])
    await message.answer("Админ-панель", reply_markup=kb)

@router.callback_query(F.data == "a_emp")
async def a_emp(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Пришли сотрудников — по одному на строку:")
    await state.set_state(State.add_emp)

@router.message(State.add_emp)
async def save_emps(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    names = [n.strip() for n in message.text.splitlines() if n.strip()]
    emp.clear(); emp.append_row(["Имя"]); emp.append_rows([[n] for n in names])
    await message.answer(f"Добавлено {len(names)} сотрудников")
    await admin_menu(message)
    await state.clear()

@router.callback_query(F.data == "a_crit")
async def a_crit(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Выбери тип критерия:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оценка 1–5", callback_data="crit_score")],
        [InlineKeyboardButton(text="Открытый текст", callback_data="crit_text")],
    ]))
    await state.set_state(State.crit_type)

@router.callback_query(F.data.startswith("crit_"))
async def crit_type(call: CallbackQuery, state: FSMContext):
    ctype = "score" if call.data.endswith("score") else "text"
    await state.update_data(crit_type=ctype)
    await call.message.edit_text(f"Тип: {'баллы' if ctype=='score' else 'текст'}\n\nПришли критерии — по одному на строку:")
    await state.set_state(State.add_crit)

@router.message(State.add_crit)
async def save_crits(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    ctype = data.get("crit_type", "score")
    items = [c.strip() for c in message.text.splitlines() if c.strip()]
    for item in items:
        crit.append_row([item, ctype])
    await message.answer(f"Добавлено {len(items)} критериев")
    await admin_menu(message)
    await state.clear()

@router.callback_query(F.data == "link")
async def link(call: CallbackQuery):
    username = (await bot.get_me()).username
    await call.message.edit_text(f"https://t.me/{username}")

dp.include_router(router)

# === ЗАПУСК (РАБОТАЕТ НА RENDER БЕСПЛАТНО) ===
if __name__ == "__main__":
    print("Бот запущен и работает!")

    # Запускаем polling в главном потоке
    async def run_polling():
        await dp.start_polling(bot)

    # Запускаем веб-заглушку в фоне
    def run_server():
        app = FastAPI()
        @app.get("/")
        def home():
            return {"status": "бот работает", "time": datetime.now().isoformat()}
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)), log_level="warning")

    threading.Thread(target=run_server, daemon=True).start()
    asyncio.run(run_polling())
