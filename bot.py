from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message 
import asyncio

TOKEN = "7819706068:AAGIGhZ36smgo_U8lci2jm9c4YEAv6r9p7Q"

bot = Bot(token=TOKEN)
router = Router()

@router.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("ЗАПИСЬ НА ВОЛЕЙБОЛ")

async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())