from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import json
import os
from datetime import datetime

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

def main_menu(user_id):
    if user_id == ADMIN_ID:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Тренировки", callback_data="list_trainings")],
            [InlineKeyboardButton(text="➕ Создать тренировку", callback_data="create_training")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Тренировки", callback_data="list_trainings")],
    ])

@router.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("🏐 Волейбол Боброво", reply_markup=main_menu(message.from_user.id))

@router.callback_query(F.data == "main_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.answer("🏐 Волейбол Боброво", reply_markup=main_menu(callback.from_user.id))
    await callback.answer()

@router.callback_query(F.data == "create_training")
async def create_training(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.answer("Введи дату и время тренировки:\nФормат: 20.06.2025 19:00")
    await state.set_state(CreateTraining.waiting_for_date)
    await callback.answer()

@router.message(CreateTraining.waiting_for_date)
async def save_training(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат! Введи так: 20.06.2025 19:00")
        return
    data = load_data()
    training = {
        "id": len(data["trainings"]) + 1,
        "date": message.text.strip(),
        "datetime": dt.isoformat(),
        "players": [],
        "waiting": [],
        "cancelled": False,
        "notified_30": False,
        "notified_10": False
    }
    data["trainings"].append(training)
    save_data(data)
    await state.clear()
    await message.answer(f"✅ Тренировка создана: {message.text.strip()}", reply_markup=main_menu(ADMIN_ID))

@router.callback_query(F.data == "list_trainings")
async def list_trainings(callback: CallbackQuery):
    data = load_data()
    active = [t for t in data["trainings"] if not t.get("cancelled")]
    if not active:
        await callback.message.answer("Нет активных тренировок", reply_markup=main_menu(callback.from_user.id))
        await callback.answer()
        return
    for t in active:
        players_count = len(t["players"])
        waiting_count = len(t["waiting"])
        text = f"📅 {t['date']}\n👥 Игроков: {players_count}/21\n⏳ Ожидание: {waiting_count}/10"
        buttons = [
            [InlineKeyboardButton(text="📋 Список", callback_data=f"view_{t['id']}")],
            [InlineKeyboardButton(text="✅ Записаться", callback_data=f"join_{t['id']}")],
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"leave_{t['id']}")],
        ]
        if callback.from_user.id == ADMIN_ID:
            buttons.append([InlineKeyboardButton(text="🚫 Отменить тренировку", callback_data=f"cancel_{t['id']}")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("view_"))
async def view_training(callback: CallbackQuery):
    training_id = int(callback.data.split("_")[1])
    data = load_data()
    t = next((x for x in data["trainings"] if x["id"] == training_id), None)
    if not t:
        await callback.answer("Не найдено")
        return
    text = f"📅 {t['date']}\n\n👥 Основной состав ({len(t['players'])}/21):\n"
    for i, p in enumerate(t["players"], 1):
        text += f"{i}. {p['name']}\n"
    if t["waiting"]:
        text += f"\n⏳ Лист ожидания ({len(t['waiting'])}/10):\n"
        for i, p in enumerate(t["waiting"], 1):
            text += f"{i}. {p['name']}\n"
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data.startswith("join_"))
async def join_training(callback: CallbackQuery):
    training_id = int(callback.data.split("_")[1])
    data = load_data()
    t = next((x for x in data["trainings"] if x["id"] == training_id), None)
    if not t or t.get("cancelled"):
        await callback.answer("Тренировка не найдена или отменена", show_alert=True)
        return
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name
    if any(p["id"] == user_id for p in t["players"] + t["waiting"]):
        await callback.answer("Ты уже записан!", show_alert=True)
        return
    if len(t["players"]) < 21:
        t["players"].append({"id": user_id, "name": user_name})
        save_data(data)
        await callback.answer(f"✅ Ты в основном составе на {t['date']}!", show_alert=True)
    elif len(t["waiting"]) < 10:
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
        await callback.answer("Не найдено", show_alert=True)
        return
    user_id = callback.from_user.id
    if any(p["id"] == user_id for p in t["players"]):
        t["players"] = [p for p in t["players"] if p["id"] != user_id]
        if t["waiting"]:
            moved = t["waiting"].pop(0)
            t["players"].append(moved)
            save_data(data)
            try:
                await bot.send_message(moved["id"], f"🎉 Ты переведён в основной состав на тренировку {t['date']}!")
            except:
                pass
        else:
            save_data(data)
        await callback.answer("✅ Запись отменена", show_alert=True)
    elif any(p["id"] == user_id for p in t["waiting"]):
        t["waiting"] = [p for p in t["waiting"] if p["id"] != user_id]
        save_data(data)
        await callback.answer("✅ Убран из листа ожидания", show_alert=True)
    else:
        await callback.answer("Ты не был записан", show_alert=True)

@router.callback_query(F.data.startswith("cancel_"))
async def cancel_training(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return
    training_id = int(callback.data.split("_")[1])
    data = load_data()
    t = next((x for x in data["trainings"] if x["id"] == training_id), None)
    if not t:
        await callback.answer("Не найдено", show_alert=True)
        return
    t["cancelled"] = True
    save_data(data)
    all_players = t["players"] + t["waiting"]
    for p in all_players:
        try:
            await bot.send_message(p["id"], f"🚫 Тренировка {t['date']} отменена администратором!")
        except:
            pass
    await callback.message.answer(f"✅ Тренировка {t['date']} отменена. Уведомления отправлены.")
    await callback.answer()

async def check_notifications():
    while True:
        now = datetime.now()
        data = load_data()
        changed = False
        for t in data["trainings"]:
            if t.get("cancelled"):
                continue
            try:
                dt = datetime.fromisoformat(t["datetime"])
            except:
                continue
            diff = (dt - now).total_seconds() / 60
            if 29 <= diff <= 31 and not t.get("notified_30"):
                t["notified_30"] = True
                changed = True
                for p in t["players"] + t["waiting"]:
                    try:
                        await bot.send_message(p["id"], f"⏰ Тренировка {t['date']} начнётся через 30 минут!")
                    except:
                        pass
            if 9 <= diff <= 11 and not t.get("notified_10"):
                t["notified_10"] = True
                changed = True
                for p in t["players"] + t["waiting"]:
                    try:
                        await bot.send_message(p["id"], f"⚡ Тренировка {t['date']} начнётся через 10 минут!")
                    except:
                        pass
        if changed:
            save_data(data)
        await asyncio.sleep(60)

async def main():
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    asyncio.create_task(check_notifications())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
