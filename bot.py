import asyncio
import os
import threading
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import gspread
from google.oauth2.service_account import Credentials

# ------------------ НАСТРОЙКИ ------------------
TOKEN = "8588765754:AAEL14w3ZK6HjCPVAOBT6obKR9YPLlDdykM"
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

# ------------------ БОТ ------------------
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_chat = State()  # ожидание вступления в чат

bot = Bot(token=TOKEN)
dp = Dispatcher()
users = {}

# ------------------ СТАРТОВОЕ СООБЩЕНИЕ ------------------
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
        "Рады видеть вас здесь!\n"
        "Скоро мы проведём вебинар «Как вернуть клиентов и увеличить доход вашего спорт‑клуба без лишнего стресса».\n\n"
        "🎁 Для участников вебинара будут эксклюзивные бонусы и специальные условия подключения!\n\n"
        "Нажмите «Зарегистрироваться» и забронируйте своё место!",
        reply_markup=keyboard
    )

# ------------------ БОЛЬШЕ О ВЕБИНАРЕ ------------------
async def send_webinar_info(user_id: int):
    info_text = (
        "🏋️ Вебинар для владельцев спорт‑клубов: «Как вернуть клиентов и увеличить доход без лишнего стресса»\n\n"
        "📌 Что проговорим:\n"
        "- Почему клиенты пропадают и как это заметить вовремя\n"
        "- 3 уровня контроля: база, поведение, деньги\n"
        "- Минимизация человеческого фактора и онлайн‑запись\n"
        "- Автоматические SMS/Push‑рассылки для удержания клиентов\n"
        "- Аналитика и статистика в одной системе\n"
        "- Как Instasport помогает управлять клубом и повышать прибыль\n\n"
        "🗓 Дата: [вставьте дату вебинара]\n"
        "⏰ Время: [вставьте время]\n\n"
        "💡 Бонус для участников: специальные условия подключения и персональные демо‑сессии."
    )
    await bot.send_message(chat_id=user_id, text=info_text)

@dp.message(lambda m: m.text == "Больше о вебинаре")
async def webinar_info(message: Message):
    await send_webinar_info(message.from_user.id)

# ------------------ FAQ ------------------
async def send_faq(user_id: int):
    faq_text = (
        "❓ FAQ по вебинару:\n\n"
        "1️⃣ Как зарегистрироваться? — Просто нажмите «Зарегистрироваться» и следуйте инструкциям.\n"
        "2️⃣ Нужно ли платить? — Нет, вебинар бесплатный.\n"
        "3️⃣ Где смотреть? — Ссылка придёт перед началом вебинара.\n"
        "4️⃣ Есть бонусы? — Да, специальные условия подключения и персональные демо-сессии для участников.\n"
    )
    await bot.send_message(chat_id=user_id, text=faq_text)

@dp.message(lambda m: m.text == "FAQ")
async def faq(message: Message):
    await send_faq(message.from_user.id)

# ------------------ РЕГИСТРАЦИЯ ------------------
@dp.message(lambda m: m.text == "Зарегистрироваться")
async def ask_name(message: Message, state: FSMContext):
    await message.answer("Напиши своё имя 👇")
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name)
async def get_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text.strip()
    if not name:
        await message.answer("Пожалуйста, введи корректное имя.")
        return
    users[user_id]["name"] = name
    await state.set_state(Registration.waiting_for_contact)

    contact_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Отлично! Теперь поделись номером телефона 👇",
        reply_markup=contact_keyboard
    )

@dp.message(Registration.waiting_for_contact, lambda m: m.contact is not None)
async def get_contact(message: Message, state: FSMContext):
    user_id = message.from_user.id
    users[user_id]["phone"] = message.contact.phone_number
    users[user_id]["registration_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    add_user_to_sheet(users[user_id])

    await message.answer(
        f"Спасибо! ✅\n\nТеперь **обязательно вступите в чат**: {CHAT_USERNAME}\n"
        "После вступления напишите /check для подтверждения регистрации на вебинар."
    )
    await state.set_state(Registration.waiting_for_chat)

# ------------------ ПРОВЕРКА ВСТУПЛЕНИЯ В ЧАТ ------------------
@dp.message(Command("check"))
async def check_chat_member(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        member = await bot.get_chat_member(CHAT_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            await message.answer(
                "🎉 Готово! Вы зарегистрированы на вебинар!\n\n"
                "Ваше место закреплено, ждём вас на эфире 🚀"
            )
            await state.clear()

            # запускаем follow-up через 1 минуту
            asyncio.create_task(send_followup(user_id))
        else:
            await message.answer(f"Ты ещё не в чате 👀\nВот ссылка: {CHAT_USERNAME}")
    except Exception as e:
        await message.answer("❌ Ошибка проверки. Бот должен быть администратором в чате.")
        print(e)

# ------------------ FOLLOW-UP ------------------
async def send_followup(user_id: int):
    await asyncio.sleep(60)
    followup_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Больше о вебинаре"), KeyboardButton(text="FAQ")]],
        resize_keyboard=True
    )
    try:
        await bot.send_message(
            chat_id=user_id,
            text="Остались вопросы?\nУзнавай больше!",
            reply_markup=followup_keyboard
        )
    except Exception as e:
        print(f"Ошибка при отправке follow-up: {e}")

# ------------------ ЗАПУСК ------------------
async def handle(request):
    return web.Response(text="Bot is running!")

def run_bot():
    asyncio.run(dp.start_polling(bot))

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8000))
    app = web.Application()
    app.router.add_get("/", handle)
    web.run_app(app, port=port)
