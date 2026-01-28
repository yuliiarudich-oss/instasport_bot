import asyncio
import os
from datetime import datetime
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import gspread
from google.oauth2.service_account import Credentials

# ------------------ ENV ------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN not found in env")

CHAT_USERNAME = "@instasport_web"
GOOGLE_SHEET_NAME = "Webinar Registrations"

# ------------------ GOOGLE SHEETS ------------------
def get_sheet():
    creds_file = os.path.join(os.path.dirname(__file__), "credentials.json")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open(GOOGLE_SHEET_NAME).sheet1

def add_user_to_sheet(user):
    sheet = get_sheet()
    sheet.append_row([
        user.get("name"),
        user.get("phone"),
        user.get("bot_start_time"),
        user.get("registration_time") or ""
    ])

# ------------------ BOT ------------------
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_chat = State()

bot = Bot(token=TOKEN)
dp = Dispatcher()
users = {}

# ------------------ START ------------------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    users[user_id] = {"bot_start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Зарегистрироваться"),
                   KeyboardButton(text="Больше о вебинаре")]],
        resize_keyboard=True
    )

    await message.answer(
        "Привет! 👋\n\n"
        "Вебинар: «Как вернуть клиентов и увеличить доход спорт-клуба без стресса»\n\n"
        "🎁 Бонусы и спецусловия для участников\n\n"
        "Нажмите «Зарегистрироваться»",
        reply_markup=keyboard
    )

# ------------------ INFO ------------------
@dp.message(lambda m: m.text == "Больше о вебинаре")
async def webinar_info(message: Message):
    await message.answer(
        "🏋️ Вебинар для владельцев клубов\n\n"
        "Темы:\n"
        "- Потери клиентов\n"
        "- Автоматизация\n"
        "- Контроль денег\n"
        "- Аналитика\n"
        "- Рост прибыли\n\n"
        "📩 Ссылка придёт перед стартом"
    )

# ------------------ REGISTRATION ------------------
@dp.message(lambda m: m.text == "Зарегистрироваться")
async def ask_name(message: Message, state: FSMContext):
    await message.answer("Введите имя:")
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name)
async def get_name(message: Message, state: FSMContext):
    users[message.from_user.id]["name"] = message.text
    await state.set_state(Registration.waiting_for_contact)

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True
    )

    await message.answer("Поделитесь номером:", reply_markup=kb)

@dp.message(Registration.waiting_for_contact, lambda m: m.contact)
async def get_contact(message: Message, state: FSMContext):
    user_id = message.from_user.id
    users[user_id]["phone"] = message.contact.phone_number
    users[user_id]["registration_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    add_user_to_sheet(users[user_id])

    await message.answer(
        f"✅ Регистрация завершена\n\nВступите в чат: {CHAT_USERNAME}\n"
        "После — напишите /check"
    )

    await state.set_state(Registration.waiting_for_chat)

# ------------------ CHECK ------------------
@dp.message(Command("check"))
async def check_chat(message: Message, state: FSMContext):
    user_id = message.from_user.id
    member = await bot.get_chat_member(CHAT_USERNAME, user_id)

    if member.status in ["member", "administrator", "creator"]:
        await message.answer("🎉 Вы зарегистрированы на вебинар!")
        await state.clear()
    else:
        await message.answer("❌ Вы ещё не в чате")

# ------------------ WEB SERVER ------------------
async def health(request):
    return web.Response(text="Bot is running")

async def main():
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
