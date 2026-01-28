import asyncio
import os
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import gspread
from google.oauth2.service_account import Credentials


# ------------------ НАСТРОЙКИ ------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в Environment Variables")

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
        user.get("name", ""),
        user.get("phone", ""),
        user.get("bot_start_time", ""),
        user.get("registration_time", "")
    ])


# ------------------ FSM ------------------
class Registration(StatesGroup):
    waiting_for_name = State()
    waiting_for_contact = State()
    waiting_for_chat = State()


# ------------------ BOT ------------------
bot = Bot(token=TOKEN)
dp = Dispatcher()
users = {}


# ------------------ /start ------------------
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    users[user_id] = {
        "bot_start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="Зарегистрироваться"),
            KeyboardButton(text="Больше о вебинаре")
        ]],
        resize_keyboard=True
    )

    await message.answer(
        "Привет! 👋\n\n"
        "Рады видеть вас здесь!\n"
        "Скоро мы проведём вебинар «Как вернуть клиентов и увеличить доход вашего спорт-клуба без лишнего стресса».\n\n"
        "🎁 Для участников вебинара будут эксклюзивные бонусы!\n\n"
        "Нажмите «Зарегистрироваться» и забронируйте место 👇",
        reply_markup=keyboard
    )


# ------------------ ИНФО О ВЕБИНАРЕ ------------------
WEBINAR_TEXT = (
    "🏋️ Вебинар для владельцев спорт-клубов\n\n"
    "📌 Что проговорим:\n"
    "- Почему клиенты пропадают\n"
    "- 3 уровня контроля\n"
    "- Онлайн-запись и автоматизация\n"
    "- SMS / Push-рассылки\n"
    "- Аналитика в одной системе\n\n"
    "💡 Бонусы и спецусловия для участников"
)


@dp.message(lambda m: m.text == "Больше о вебинаре")
async def webinar_info(message: Message):
    await message.answer(WEBINAR_TEXT)


# ------------------ FAQ ------------------
FAQ_TEXT = (
    "❓ FAQ\n\n"
    "1️⃣ Вебинар бесплатный\n"
    "2️⃣ Ссылка придёт перед стартом\n"
    "3️⃣ Будут бонусы и демо\n"
)


@dp.message(lambda m: m.text == "FAQ")
async def faq(message: Message):
    await message.answer(FAQ_TEXT)


# ------------------ РЕГИСТРАЦИЯ ------------------
@dp.message(lambda m: m.text == "Зарегистрироваться")
async def ask_name(message: Message, state: FSMContext):
    await message.answer("Напиши своё имя 👇")
    await state.set_state(Registration.waiting_for_name)


@dp.message(Registration.waiting_for_name)
async def get_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    users[user_id]["name"] = message.text.strip()

    contact_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        "Теперь поделись номером телефона 👇",
        reply_markup=contact_keyboard
    )
    await state.set_state(Registration.waiting_for_contact)


@dp.message(Registration.waiting_for_contact)
async def get_contact(message: Message, state: FSMContext):
    if not message.contact:
        await message.answer("Нажми кнопку «Поделиться контактом» ⬇️")
        return

    user_id = message.from_user.id
    users[user_id]["phone"] = message.contact.phone_number
    users[user_id]["registration_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    add_user_to_sheet(users[user_id])

    await message.answer(
        f"✅ Почти готово!\n\n"
        f"Обязательно вступи в чат: {CHAT_USERNAME}\n"
        "После этого напиши /check"
    )

    await state.set_state(Registration.waiting_for_chat)


# ------------------ ПРОВЕРКА ЧАТА ------------------
@dp.message(Command("check"))
async def check_chat(message: Message, state: FSMContext):
    user_id = message.from_user.id

    try:
        member = await bot.get_chat_member(CHAT_USERNAME, user_id)
        if member.status in ("member", "administrator", "creator"):
            await message.answer(
                "🎉 Вы зарегистрированы!\n"
                "Ждём вас на вебинаре 🚀"
            )
            await state.clear()
            asyncio.create_task(send_followup(user_id))
        else:
            await message.answer("Вы ещё не вступили в чат 👀")
    except Exception:
        await message.answer("❌ Бот должен быть администратором чата")


# ------------------ FOLLOW UP ------------------
async def send_followup(user_id: int):
    await asyncio.sleep(60)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Больше о вебинаре"), KeyboardButton(text="FAQ")]],
        resize_keyboard=True
    )

    await bot.send_message(
        user_id,
        "Остались вопросы?\nУзнавай больше 👇",
        reply_markup=keyboard
    )


# ------------------ ЗАПУСК ------------------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


