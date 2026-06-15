from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import json
import os

TOKEN = "7819706068:AAGIGhZ36smgo_U8lci2jm9c4YEAv6r9p7Q"
ADMIN_ID = 7423253055

bot = Bot(token=TOKEN)
router = Router()
storage = MemoryStorage()

DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"trainings": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class CreateTraining(StatesGroup):
    waiting_for_date = State()

@router.message(Command("start"))
async def start_handler(message: Message):
    if message.from_user.id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Тренировки", callback_data="list_trainings")],
            [InlineKeyboardButton(text="➕ Создать тренировку", callback_data="create_training")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        ])
        await message.answer("🏐 Волейбол Боброво — Админ панель", reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Тренировки", callback_data="list_trainings")],
        ])
        await message.answer("🏐 Добро пожаловать в Волейбол Боброво!\nВыбери действие:", reply_markup=kb)

@router.callback_query(F.data == "create_training")
async def create_training(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.answer("Введи дату и время тренировки:\nНапример: 20 июня 19:00")
    await state.set_state(CreateTraining.waiting_for_date)
    await callback.answer()

@router.message(CreateTraining.waiting_for_date)
async def save_training(message: Message, state: FSMContext):
    data = load_data()
    training = {
        "id": len(data["trainings"]) + 1,
        "date": message.text,
        "players": [],
        "waiting": []
    }
    data["trainings"].append(training)
    save_data(data)
    await state.clear()
    await message.answer(f"✅ Тренировка создана: {message.text}")

@router.callback_query(F.data == "list_trainings")
async def list_trainings(callback: CallbackQuery):
    data = load_data()
    if not data["trainings"]:
        await callback.message.answer("Нет тренировок")
        await callback.answer()
        return
    for t in data["trainings"]:
        players_count = len(t["players"])
        waiting_count = len(t["waiting"])
        text = f"📅 {t['date']}\n👥 Игроков: {players_count}/18\n⏳ Ожидание: {waiting_count}/3"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список", callback_data=f"view_{t['id']}")],
            [InlineKeyboardButton(text="✅ Записаться", callback_data=f"join_{t['id']}")],
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"leave_{t['id']}")],
        ])
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("view_"))
async def view_training(callback: CallbackQuery):
    training_id = int(callback.data.split("_")[1])
    data = load_data()
    t = next((x for x in data["trainings"] if x["id"] == training_id), None)
    if not t:
        await callback.answer("Тренировка не найдена")
        return
    text = f"📅 Тренировка: {t['date']}\n\n"
    text += "👥 Основной состав:\n"
    for i, p in enumerate(t["players"], 1):
        text += f"{i}. {p['name']}\n"
    if t["waiting"]:
        text += "\n⏳ Лист ожидания:\n"
        for i, p in enumerate(t["waiting"], len(t["players"]) + 1):
            text += f"{i}. {p['name']}\n"
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data.startswith("join_"))
async def join_training(callback: CallbackQuery):
    training_id = int(callback.data.split("_")[1])
    data = load_data()
    t = next((x for x in data["trainings"] if x["id"] == training_id), None)
    if not t:
        await callback.answer("Тренировка не найдена")
        return
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name
    all_players = t["players"] + t["waiting"]
    if any(p["id"] == user_id for p in all_players):
        await callback.answer("Ты уже записан!", show_alert=True)
        return
    if len(t["players"]) < 18:
        t["players"].append({"id": user_id, "name": user_name})
        save_data(data)
        await callback.answer(f"✅ Ты записан на {t['date']}!", show_alert=True)
    elif len(t["waiting"]) < 3:
        t["waiting"].append({"id": user_id, "name": user_name})
        save_data(data)
        await callback.answer(f"⏳ Ты в листе ожидания на {t['date']}!", show_alert=True)
    else:
        await callback.answer("❌ Все места заняты!", show_alert=True)

@router.callback_query(F.data.startswith("leave_"))
async def leave_training(callback: CallbackQuery):
    training_id = int(callback.data.split("_")[1])
    data = load_data()
    t = next((x for x in data["trainings"] if x["id"] == training_id), None)
    if not t:
        await callback.answer("Тренировка не найдена")
        return
    user_id = callback.from_user.id
    if any(p["id"] == user_id for p in t["players"]):
        t["players"] = [p for p in t["players"] if p["id"] != user_id]
        if t["waiting"]:
            t["players"].append(t["waiting"].pop(0))
        save_data(data)
        await callback.answer("✅ Запись отменена", show_alert=True)
    elif any(p["id"] == user_id for p in t["waiting"]):
        t["waiting"] = [p for p in t["waiting"] if p["id"] != user_id]
        save_data(data)
        await callback.answer("✅ Убран из листа ожидания", show_alert=True)
    else:
        await callback.answer("Ты не был записан", show_alert=True)

@router.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    data = load_data()
    text = f"📊 Статистика:\nВсего тренировок: {len(data['trainings'])}"
    await callback.message.answer(text)
    await callback.answer()

async def main():
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
