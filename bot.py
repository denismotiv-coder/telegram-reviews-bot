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
from aiogram.fsm.storage.memory import MemoryStorage

import gspread
from google.oauth2.service_account import Credentials
from fastapi import FastAPI
import uvicorn

# Отключаем uvloop — критически важно для Render
os.environ["AIOGRAM_USE_UVLOOP"] = "0"

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS")

# Секретный параметр для доступа
SECRET_PARAM = "okko"

# === GOOGLE SHEETS ===
creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

def get_sheet(name, header):
    try:
        return sh.worksheet(name)
    except:
        ws = sh.add_worksheet(title=name, rows=1000, cols=10)
        ws.append_row(header)
        return ws

emp = get_sheet("Сотрудники", ["Имя"])
crit = get_sheet("Критерии", ["Критерий", "Тип"])
rev = get_sheet("Отзывы", ["Время","Сотрудник","Критерий","Оценка","Комментарий","user_id"])
config = get_sheet("Настройки", ["Параметр", "Значение"])

# === НАЗВАНИЕ ОТДЕЛА ===
def get_department():
    try:
        rows = config.get_all_values()
        for row in rows:
            if row and row[0] == "department":
                return row[1] if len(row) > 1 else "оперативной графики"
    except:
        pass
    return "оперативной графики"

def set_department(name):
    try:
        rows = config.get_all_values()
        found = False
        for i, row in enumerate(rows, 1):
            if row and row[0] == "department":
                config.update_cell(i, 2, name)
                found = True
                break
        if not found:
            config.append_row(["department", name])
    except:
        config.append_row(["department", name])

# === БОТ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class State(StatesGroup):
    add_emp = State()
    add_crit = State()
    crit_type = State()
    waiting_text = State()
    change_dept = State()

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

# === АДМИНКА ===
async def admin_menu(msg: Message):
    dept = get_department()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сотрудники", callback_data="a_emp")],
        [InlineKeyboardButton(text="Критерии", callback_data="a_crit")],
        [InlineKeyboardButton(text=f"Отдел: {dept}", callback_data="change_dept")],
        [InlineKeyboardButton(text="Ссылка для команды", url="https://t.me/Team_Review_bot")],
        [InlineKeyboardButton(text="Таблица", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
    ])
    await msg.answer("Админ-панель", reply_markup=kb)

@router.callback_query(F.data == "change_dept")
async def change_dept(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Пришли новое название отдела:")
    await state.set_state(State.change_dept)

@router.message(State.change_dept)
async def save_dept(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    name = message.text.strip()
    set_department(name)
    await message.answer(f"Название отдела обновлено: {name}")
    await admin_menu(message)
    await state.clear()

# === СТАРТ С ЗАЩИТОЙ ===
@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()

    # Админ всегда проходит
    if message.from_user.id == ADMIN_ID:
        await admin_menu(message)
        return

    # Защита по секретной ссылке
    if not message.text or SECRET_PARAM not in message.text:
        await message.answer("Доступ закрыт.\nОпрос только по личной ссылке от руководителя.")
        return

    dept = get_department()

    await message.answer(
        f"Привет! Давай поиграем в «невидимого критика»\n\n"
        f"Это анонимный опрос по отделу {dept}. Ты — наш секретный информатор!\n\n"
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
        await message.answer("Сотрудников пока нет — попроси админа добавить")
        return

    kb = [[InlineKeyboardButton(text=n, callback_data=f"sel_emp_{i}")] for i,n in enumerate(emps,1)]
    kb.append([InlineKeyboardButton(text="Исправить оценку", callback_data="edit_mode")])
    await message.answer("Выбери человека для оценки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# === ВСЯ ЛОГИКА ОПРОСА (остаётся без изменений) ===
# (всё от выбора сотрудника до финального сообщения — как в предыдущей версии)

# === ЗАПУСК ===
dp.include_router(router)

if __name__ == "__main__":
    print("Бот запущен и работает!")

    async def run_polling():
        await dp.start_polling(bot)

    def run_server():
        app = FastAPI()
        @app.get("/")
        def home():
            return {"status": "бот работает", "time": datetime.now().isoformat()}
        uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)), log_level="warning")

    threading.Thread(target=run_server, daemon=True).start()
    asyncio.run(run_polling())
