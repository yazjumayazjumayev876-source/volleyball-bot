from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import json
import os
import random
from datetime import datetime, date

from words_data import WORDS, LEVELS_ORDER

TOKEN = "СЮДА_ВСТАВЬ_СВОЙ_ТОКЕН"

bot = Bot(token=TOKEN)
router = Router()
storage = MemoryStorage()

DATA_FILE = "users.json"

# ---------- хранение данных ----------

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "level": None,
            "level_confirmed": None,
            "goal": None,
            "daily_time": None,
            "lessons_done": 0,
            "learned_words": [],
            "current_lesson_words": [],
            "current_lesson_index": 0,
            "last_active": None,
            "deadline_months": None,
            "test_state": None,
        }
    return data[uid]

# ---------- состояния ----------

class Onboarding(StatesGroup):
    waiting_level_test_answer = State()
    waiting_lesson_answer = State()
    waiting_quiz_answer = State()

GOALS = [
    "Работа и карьера",
    "Путешествия",
    "Экзамен (IELTS/TOEFL)",
    "Переезд за границу",
    "Учёба / университет",
    "Для себя / хобби",
]

TIME_OPTIONS = ["15 минут", "30 минут", "1 час"]

# ---------- уровень-тест (5 вопросов на проверку заявленного уровня) ----------

def generate_level_test(level: str):
    """Создаёт 5 вопросов по словам заявленного уровня для проверки."""
    pool = WORDS.get(level, WORDS["Beginner"])
    sample = random.sample(pool, min(5, len(pool)))
    questions = []
    all_words_flat = [w for lvl in WORDS.values() for w in lvl]
    for word_en, word_ru in sample:
        wrong_options = random.sample(
            [w[1] for w in all_words_flat if w[1] != word_ru], 3
        )
        options = wrong_options + [word_ru]
        random.shuffle(options)
        questions.append({
            "question": f"Переведи слово: {word_en}",
            "options": options,
            "correct": word_ru,
        })
    return questions

# ---------- клавиатуры ----------

def levels_kb():
    buttons = [[InlineKeyboardButton(text=lvl, callback_data=f"level_{lvl}")] for lvl in LEVELS_ORDER]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def goals_kb():
    buttons = [[InlineKeyboardButton(text=g, callback_data=f"goal_{i}")] for i, g in enumerate(GOALS)]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def time_kb():
    buttons = [[InlineKeyboardButton(text=t, callback_data=f"time_{t}")] for t in TIME_OPTIONS]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Новый урок", callback_data="start_lesson")],
        [InlineKeyboardButton(text="📊 Мой прогресс", callback_data="progress")],
    ])

def answer_options_kb(options, prefix):
    buttons = [[InlineKeyboardButton(text=opt, callback_data=f"{prefix}_{opt}")] for opt in options]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------- /start ----------

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    data = load_data()
    user = get_user(data, message.from_user.id)
    save_data(data)

    if user["level_confirmed"]:
        await message.answer(
            f"Привет! 👋 Продолжаем изучение английского.\nТвой уровень: {user['level_confirmed']}\nПройдено уроков: {user['lessons_done']}",
            reply_markup=main_menu_kb()
        )
        return

    await message.answer(
        "👋 Привет! Я твой персональный преподаватель английского.\n\n"
        "Сначала узнаем твой уровень. Как ты сам оцениваешь свои знания английского? 📶",
        reply_markup=levels_kb()
    )

# ---------- выбор заявленного уровня ----------

@router.callback_query(F.data.startswith("level_"))
async def chosen_level(callback: CallbackQuery, state: FSMContext):
    level = callback.data.replace("level_", "")
    data = load_data()
    user = get_user(data, callback.from_user.id)
    user["level"] = level
    test = generate_level_test(level)
    user["test_state"] = {"questions": test, "index": 0, "correct": 0, "type": "level_check"}
    save_data(data)

    await callback.message.answer(
        f"Ты выбрал уровень: {level}.\nПроверим, насколько это так — мини-тест из 5 вопросов!"
    )
    await ask_next_test_question(callback.message, callback.from_user.id)
    await callback.answer()

async def ask_next_test_question(message: Message, user_id: int):
    data = load_data()
    user = get_user(data, user_id)
    ts = user["test_state"]
    idx = ts["index"]
    if idx >= len(ts["questions"]):
        await finish_level_test(message, user_id)
        return
    q = ts["questions"][idx]
    await message.answer(
        f"Вопрос {idx + 1}/{len(ts['questions'])}\n{q['question']}",
        reply_markup=answer_options_kb(q["options"], "leveltest")
    )

@router.callback_query(F.data.startswith("leveltest_"))
async def level_test_answer(callback: CallbackQuery):
    answer = callback.data.replace("leveltest_", "")
    data = load_data()
    user = get_user(data, callback.from_user.id)
    ts = user["test_state"]
    if not ts or ts.get("type") != "level_check":
        await callback.answer()
        return
    idx = ts["index"]
    q = ts["questions"][idx]
    if answer == q["correct"]:
        ts["correct"] += 1
        await callback.answer("✅ Верно!")
    else:
        await callback.answer(f"❌ Неверно. Правильно: {q['correct']}")
    ts["index"] += 1
    save_data(data)
    await ask_next_test_question(callback.message, callback.from_user.id)

async def finish_level_test(message: Message, user_id: int):
    data = load_data()
    user = get_user(data, user_id)
    ts = user["test_state"]
    correct = ts["correct"]
    total = len(ts["questions"])
    declared_level = user["level"]
    idx_declared = LEVELS_ORDER.index(declared_level)

    # если справился плохо (меньше 60%) — снижаем уровень на 1, если справился отлично (100%) и уровень не топ — можно оставить как есть
    if correct / total < 0.6 and idx_declared > 0:
        real_level = LEVELS_ORDER[idx_declared - 1]
        msg = f"По результатам теста ({correct}/{total}) твой реальный уровень похож на: {real_level}, а не {declared_level}. Начнём с {real_level}!"
    else:
        real_level = declared_level
        msg = f"Отлично, результат теста {correct}/{total} подтверждает твой уровень: {declared_level}!"

    user["level_confirmed"] = real_level
    user["test_state"] = None
    save_data(data)

    await message.answer(msg)
    await message.answer(
        "Теперь скажи — для чего тебе нужен английский? 🎯",
        reply_markup=goals_kb()
    )

# ---------- цель ----------

@router.callback_query(F.data.startswith("goal_"))
async def chosen_goal(callback: CallbackQuery):
    goal_idx = int(callback.data.replace("goal_", ""))
    goal = GOALS[goal_idx]
    data = load_data()
    user = get_user(data, callback.from_user.id)
    user["goal"] = goal
    save_data(data)

    await callback.message.answer(
        f"Цель: {goal}. Понял! 💪\n\nСколько времени в день готов уделять английскому?",
        reply_markup=time_kb()
    )
    await callback.answer()

# ---------- время на учёбу ----------

@router.callback_query(F.data.startswith("time_"))
async def chosen_time(callback: CallbackQuery):
    time_choice = callback.data.replace("time_", "")
    data = load_data()
    user = get_user(data, callback.from_user.id)
    user["daily_time"] = time_choice

    # прикидываем срок обучения исходя из уровня и времени в день
    level_idx = LEVELS_ORDER.index(user["level_confirmed"])
    levels_to_go = len(LEVELS_ORDER) - level_idx
    time_factor = {"15 минут": 1.5, "30 минут": 1.0, "1 час": 0.6}[time_choice]
    months = max(2, round(levels_to_go * 3 * time_factor))
    user["deadline_months"] = months
    save_data(data)

    await callback.message.answer(
        f"Отлично! При {time_choice} в день, я думаю, мы дойдём до свободного владения примерно через {months} месяцев. 🚀\n\n"
        f"Источник слов и материалов — я сам подобрал тебе слова под твой уровень ({user['level_confirmed']}), всё уже готово в базе.\n\n"
        f"Начинаем учиться карточками! Каждый урок — 5 новых слов. После 5 уроков — мини-тест на 20 вопросов, после 10 уроков — тест на 40 вопросов.",
        reply_markup=main_menu_kb()
    )
    await callback.answer()

# ---------- запуск урока ----------

@router.callback_query(F.data == "start_lesson")
async def start_lesson(callback: CallbackQuery):
    data = load_data()
    user = get_user(data, callback.from_user.id)

    if not user["level_confirmed"]:
        await callback.answer("Сначала пройди регистрацию через /start", show_alert=True)
        return

    level = user["level_confirmed"]
    pool = WORDS.get(level, WORDS["Beginner"])
    learned = set(user["learned_words"])
    available = [w for w in pool if w[0] not in learned]

    if len(available) < 5:
        # если слов уровня не хватает - переходим на след. уровень
        idx = LEVELS_ORDER.index(level)
        if idx + 1 < len(LEVELS_ORDER):
            level = LEVELS_ORDER[idx + 1]
            user["level_confirmed"] = level
            pool = WORDS.get(level, [])
            available = [w for w in pool if w[0] not in learned]
        if len(available) < 5:
            await callback.message.answer("🎉 Похоже, ты выучил все доступные слова! Скоро добавим больше материала.")
            await callback.answer()
            return

    lesson_words = random.sample(available, 5)
    user["current_lesson_words"] = lesson_words
    user["current_lesson_index"] = 0
    user["last_active"] = date.today().isoformat()
    save_data(data)

    await callback.message.answer(f"📚 Новый урок! 5 новых слов ({level}).")
    await show_lesson_card(callback.message, callback.from_user.id)
    await callback.answer()

async def show_lesson_card(message: Message, user_id: int):
    data = load_data()
    user = get_user(data, user_id)
    idx = user["current_lesson_index"]
    words = user["current_lesson_words"]

    if idx >= len(words):
        user["lessons_done"] += 1
        for w in words:
            if w[0] not in user["learned_words"]:
                user["learned_words"].append(w[0])
        save_data(data)

        await message.answer(f"✅ Урок завершён! Всего пройдено уроков: {user['lessons_done']}")

        if user["lessons_done"] % 10 == 0:
            await start_quiz(message, user_id, 40)
        elif user["lessons_done"] % 5 == 0:
            await start_quiz(message, user_id, 20)
        else:
            await message.answer("Можешь пройти следующий урок когда захочешь!", reply_markup=main_menu_kb())
        return

    word_en, word_ru = words[idx]
    # смешиваем направление перевода
    direction = random.choice(["en_to_ru", "ru_to_en"])
    all_words_flat = [w for lvl in WORDS.values() for w in lvl]

    if direction == "en_to_ru":
        wrong = random.sample([w[1] for w in all_words_flat if w[1] != word_ru], 3)
        options = wrong + [word_ru]
        random.shuffle(options)
        user["test_state"] = {"type": "lesson_card", "correct": word_ru, "direction": direction}
        text = f"Карточка {idx + 1}/5\n\n🇬🇧 {word_en}\n\nКакой перевод правильный?"
    else:
        wrong = random.sample([w[0] for w in all_words_flat if w[0] != word_en], 3)
        options = wrong + [word_en]
        random.shuffle(options)
        user["test_state"] = {"type": "lesson_card", "correct": word_en, "direction": direction}
        text = f"Карточка {idx + 1}/5\n\n🇷🇺 {word_ru}\n\nКакое слово правильное?"

    save_data(data)
    await message.answer(text, reply_markup=answer_options_kb(options, "lessoncard"))

@router.callback_query(F.data.startswith("lessoncard_"))
async def lesson_card_answer(callback: CallbackQuery):
    answer = callback.data.replace("lessoncard_", "")
    data = load_data()
    user = get_user(data, callback.from_user.id)
    ts = user["test_state"]
    if not ts or ts.get("type") != "lesson_card":
        await callback.answer()
        return

    if answer == ts["correct"]:
        await callback.answer("✅ Верно!")
    else:
        await callback.answer(f"❌ Неверно. Правильно: {ts['correct']}")

    user["current_lesson_index"] += 1
    save_data(data)
    await show_lesson_card(callback.message, callback.from_user.id)

# ---------- мини-тесты после 5/10 уроков ----------

async def start_quiz(message: Message, user_id: int, num_questions: int):
    data = load_data()
    user = get_user(data, user_id)
    learned = user["learned_words"]

    all_words_flat = [w for lvl in WORDS.values() for w in lvl]
    learned_pairs = [w for w in all_words_flat if w[0] in learned]

    if len(learned_pairs) < 4:
        await message.answer("Недостаточно слов для теста пока, продолжай учиться!", reply_markup=main_menu_kb())
        return

    sample_size = min(num_questions, len(learned_pairs))
    sample = random.sample(learned_pairs, sample_size)
    # если слов меньше чем нужно вопросов - повторяем некоторые
    questions = []
    while len(questions) < num_questions and learned_pairs:
        word_en, word_ru = random.choice(learned_pairs)
        direction = random.choice(["en_to_ru", "ru_to_en"])
        if direction == "en_to_ru":
            wrong = random.sample([w[1] for w in all_words_flat if w[1] != word_ru], min(3, len(all_words_flat)-1))
            options = wrong + [word_ru]
            random.shuffle(options)
            questions.append({"question": f"Переведи слово: {word_en}", "options": options, "correct": word_ru})
        else:
            wrong = random.sample([w[0] for w in all_words_flat if w[0] != word_en], min(3, len(all_words_flat)-1))
            options = wrong + [word_en]
            random.shuffle(options)
            questions.append({"question": f"Какое слово значит: {word_ru}?", "options": options, "correct": word_en})

    user["test_state"] = {"type": "quiz", "questions": questions, "index": 0, "correct": 0}
    save_data(data)

    await message.answer(f"📝 Мини-экзамен! {num_questions} вопросов по всем пройденным словам (вперемешку).")
    await ask_next_quiz_question(message, user_id)

async def ask_next_quiz_question(message: Message, user_id: int):
    data = load_data()
    user = get_user(data, user_id)
    ts = user["test_state"]
    idx = ts["index"]
    if idx >= len(ts["questions"]):
        await finish_quiz(message, user_id)
        return
    q = ts["questions"][idx]
    await message.answer(
        f"Вопрос {idx + 1}/{len(ts['questions'])}\n{q['question']}",
        reply_markup=answer_options_kb(q["options"], "quiz")
    )

@router.callback_query(F.data.startswith("quiz_"))
async def quiz_answer(callback: CallbackQuery):
    answer = callback.data.replace("quiz_", "")
    data = load_data()
    user = get_user(data, callback.from_user.id)
    ts = user["test_state"]
    if not ts or ts.get("type") != "quiz":
        await callback.answer()
        return
    idx = ts["index"]
    q = ts["questions"][idx]
    if answer == q["correct"]:
        ts["correct"] += 1
        await callback.answer("✅ Верно!")
    else:
        await callback.answer(f"❌ Неверно. Правильно: {q['correct']}")
    ts["index"] += 1
    save_data(data)
    await ask_next_quiz_question(callback.message, callback.from_user.id)

async def finish_quiz(message: Message, user_id: int):
    data = load_data()
    user = get_user(data, user_id)
    ts = user["test_state"]
    correct = ts["correct"]
    total = len(ts["questions"])
    percent = round(correct / total * 100)
    user["test_state"] = None
    save_data(data)

    await message.answer(
        f"🏁 Тест завершён! Результат: {correct}/{total} ({percent}%)\n\nПродолжаем учиться!",
        reply_markup=main_menu_kb()
    )

# ---------- прогресс ----------

@router.callback_query(F.data == "progress")
async def show_progress(callback: CallbackQuery):
    data = load_data()
    user = get_user(data, callback.from_user.id)
    text = (
        f"📊 Твой прогресс:\n\n"
        f"Уровень: {user['level_confirmed']}\n"
        f"Цель: {user['goal']}\n"
        f"Время в день: {user['daily_time']}\n"
        f"Уроков пройдено: {user['lessons_done']}\n"
        f"Слов выучено: {len(user['learned_words'])}\n"
        f"Примерный срок до цели: {user['deadline_months']} мес."
    )
    await callback.message.answer(text, reply_markup=main_menu_kb())
    await callback.answer()

# ---------- ежедневные напоминания ----------

async def daily_reminders():
    while True:
        data = load_data()
        today = date.today().isoformat()
        for uid, user in data.items():
            if not user.get("level_confirmed"):
                continue
            last_active = user.get("last_active")
            if last_active != today:
                try:
                    await bot.send_message(
                        int(uid),
                        "👋 Не забывай про английский! Загляни на урок сегодня 📚",
                        reply_markup=main_menu_kb()
                    )
                except Exception:
                    pass
        await asyncio.sleep(24 * 60 * 60)  # раз в сутки

# ---------- запуск ----------

async def main():
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    asyncio.create_task(daily_reminders())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
