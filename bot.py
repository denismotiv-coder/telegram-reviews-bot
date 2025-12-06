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
def get_sheet(name, header):
    try: return sh.worksheet(name)
    except:
        ws = sh.add_worksheet(title=name, rows=1000, cols=10)
        ws.append_row(header)
        return ws

emp_sheet = get_sheet("Сотрудники", ["Имя"])
crit_sheet = get_sheet("Критерии", ["Критерий", "Тип"])  # score или text
rev_sheet = get_sheet("Отзывы", ["Время","Сотрудник","Критерий","Оценка","Комментарий","user_id"])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class AdminState(StatesGroup):
    add_emp = State()
    add_crit = State()
    crit_type = State()

class UserState(StatesGroup):
    normal_flow = State()      # обычный опрос
    editing_flow = State()     # режим исправления
    waiting_text = State()

# === ВСПОМОГАТЕЛЬНЫЕ ===
def get_employees():
    return [r[0] for r in emp_sheet.get_all_values()[1:] if r and r[0].strip()]

def get_criteria():
    rows = crit_sheet.get_all_values()[1:]
    return [(r[0], r[1] if len(r)>1 else "score") for r in rows if r and r[0].strip()]

def delete_user_reviews(user_id: int, employee: str = None):
    """Удаляет все оценки пользователя (или только по одному сотруднику)"""
    rows = rev_sheet.get_all_values()
    header = rows[0]
    user_col = header.index("user_id") + 1
    emp_col = header.index("Сотрудник") + 1 if "Сотрудник" in header else -1

    to_delete = []
    for i, row in enumerate(rows[1:], 2):
        if row and len(row) >= user_col and row[user_col-1].endswith(str(user_id)):
            if employee is None or (emp_col > 0 and row[emp_col-1] == employee):
                to_delete.append(i)
    if to_delete:
        for row in reversed(to_delete):
            rev_sheet.delete_rows(row)

async def show_employee_list(message: Message, state: FSMContext, editing: bool = False):
    employees = get_employees()
    if not employees:
        await message.answer("Сотрудников нет")
        return

    kb = []
    for i, name in enumerate(employees, 1):
        kb.append([InlineKeyboardButton(text=name, callback_data=f"{'edit' if editing else 'sel'}_emp_{i}")])

    if not editing:
        kb.append([InlineKeyboardButton(text="Исправить оценку", callback_data="start_edit")])

    await message.answer(
        "Выбери следующего" if not editing else "Кого хочешь переоценить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )
    await state.set_state(UserState.normal_flow if not editing else UserState.editing_flow)

# === СТАРТ ===
@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        await admin_menu(message)
        return

    await message.answer(
        "Привет! Давай поиграем в «невидимого критика»\n"
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
    await show_employee_list(message, state, editing=False)

# === АДМИНКА ===
async def admin_menu(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сотрудники", callback_data="admin_emp")],
        [InlineKeyboardButton(text="Критерии", callback_data="admin_crit")],
        [InlineKeyboardButton(text="Ссылка для команды", callback_data="get_link")],
        [InlineKeyboardButton(text="Таблица результатов", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")],
    ])
    await message.answer("Админ-панель", reply_markup=kb)

# (остальные админ-функции — без изменений, как в прошлом сообщении)

# === ИСПРАВЛЕНИЕ ОЦЕНОК ===
@router.callback_query(F.data == "start_edit")
async def start_edit(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Режим исправления оценок включён")
    await show_employee_list(call.message, state, editing=True)

# === ВЫБОР СОТРУДНИКА (обычный или редактирование) ===
@router.callback_query(F.data.startswith(("sel_emp_", "edit_emp_")))
async def select_employee(call: CallbackQuery, state: FSMContext):
    is_edit = call.data.startswith("edit_emp_")
    idx = int(call.data.split("_")[-1])
    employee = emp_sheet.row_values(idx)[0]

    # При редактировании — удаляем старые оценки этого пользователя по этому человеку
    if is_edit:
        delete_user_reviews(call.from_user.id, employee)

    await state.update_data(employee=employee, crit_idx=0, is_edit=is_edit)
    await next_criterion(call.message, state)

# === СЛЕДУЮЩИЙ КРИТЕРИЙ ===
async def next_criterion(message: Message, state: FSMContext):
    data = await state.get_data()
    employee = data["employee"]
    criteria = get_criteria()
    idx = data.get("crit_idx", 0)

    if idx >= len(criteria):
        # Все критерии пройдены
        if data.get("is_edit"):
            await message.edit_text("Оценка обновлена! Спасибо ❤️")
            await asyncio.sleep(2)
            await show_employee_list(message, state, editing=False)
        else:
            remaining = [e for e in get_employees() if e != employee]
            if not remaining:
                await message.edit_text(
                    "Спасибо большое за твою оценку!\n\n"
                    "Напоминаю: это был полностью анонимный опрос. Никто не узнает, что именно ты написал — только общие цифры.\n"
                    "Твой вклад реально помогает команде становиться лучше!\n\n"
                    "Разработал бот: Кульбацкий Денис (@Motiv33)"
                )
                await state.clear()
            else:
                await message.edit_text("Выбери следующего", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=n, callback_data=f"sel_emp_{i}")] for i,n in enumerate(remaining,1)
                ]))
        return

    crit_name, crit_type = criteria[idx]
    if crit_type == "score":
        kb = [[InlineKeyboardButton(text=f"{i}⭐", callback_data=f"rate_{i}_{idx}")] for i in range(1,6)]
        text = f"Оцениваем: {employee}\nКритерий: {crit_name}\n\nОценка от 1 до 5:"
    else:
        kb = [[InlineKeyboardButton(text="Пропустить", callback_data=f"skip_{idx}")],
              [InlineKeyboardButton(text="Написать комментарий", callback_data=f"text_{idx}")]]
        text = f"Оцениваем: {employee}\nКритерий: {crit_name}\n\n(по желанию)"

    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# === ОТВЕТЫ ===
@router.callback_query(F.data.startswith(("rate_", "skip_", "text_")))
async def handle_answer(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    idx = int(call.data.split("_")[1])
    crit_name, _ = get_criteria()[idx]

    if call.data.startswith("rate_"):
        score = call.data.split("_")[1]
        rev_sheet.append_row([datetime.now().strftime("%d.%m %H:%M"), data["employee"], crit_name, score, "", f"user_{call.from_user.id}"])
    elif call.data.startswith("text_"):
        await call.message.edit_text(f"Напиши комментарий по пункту «{crit_name}»:")
        await state.update_data(waiting_crit_idx=idx)
        await state.set_state(UserState.waiting_text)
        return
    # skip — ничего

    await state.update_data(crit_idx=idx + 1)
    await next_criterion(call.message, state)

@router.message(UserState.waiting_text)
async def save_text(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data["waiting_crit_idx"]
    crit_name, _ = get_criteria()[idx]
    rev_sheet.append_row([datetime.now().strftime("%d.%m %H:%M"), data["employee"], crit_name, "", message.text, f"user_{message.from_user.id}"])
    await message.answer("Комментарий сохранён!")
    await state.update_data(crit_idx=idx + 1)
    await next_criterion(message, state)

# === ЗАПУСК ===
dp.include_router(router)

if __name__ == "__main__":
    print("Бот запущен!")
    asyncio.run(dp.start_polling(bot))
