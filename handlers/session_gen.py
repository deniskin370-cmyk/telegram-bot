"""
Генерация USERBOT_SESSION прямо через Telegram-бота.

Только для CREATOR_ID. Команда: .gensession
Бот проведёт через ввод номера и кода и пришлёт готовую строку сессии.
"""
import logging

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from pyrogram import Client
from pyrogram.errors import (
    PhoneCodeInvalid, PhoneCodeExpired,
    SessionPasswordNeeded, PhoneNumberInvalid,
)

from config import CREATOR_ID, USERBOT_API_ID, USERBOT_API_HASH

logger = logging.getLogger(__name__)
router = Router()

# FSM-состояния
class SessionGen(StatesGroup):
    waiting_phone = State()
    waiting_code  = State()
    waiting_2fa   = State()


# Временное хранилище клиента и phone_code_hash между шагами
_clients: dict[int, dict] = {}


@router.message(F.text == ".gensession")
async def cmd_gensession(message: Message, state: FSMContext):
    if message.from_user.id != CREATOR_ID:
        return

    if not USERBOT_API_ID or not USERBOT_API_HASH:
        await message.answer(
            "❌ <b>USERBOT_API_ID</b> или <b>USERBOT_API_HASH</b> не заданы в Variables на Railway.\n\n"
            "Добавь их и перезапусти бота.",
            parse_mode="HTML",
        )
        return

    await state.set_state(SessionGen.waiting_phone)
    await message.answer(
        "📱 <b>Генерация сессии Pyrogram</b>\n\n"
        "Введи номер телефона в формате:\n<code>+79991234567</code>",
        parse_mode="HTML",
    )


@router.message(SessionGen.waiting_phone)
async def handle_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    user_id = message.from_user.id

    await message.answer("⏳ Отправляю код...")

    try:
        client = Client(
            name=f"gen_{user_id}",
            api_id=USERBOT_API_ID,
            api_hash=USERBOT_API_HASH,
            in_memory=True,
        )
        await client.connect()
        sent = await client.send_code(phone)
    except PhoneNumberInvalid:
        await message.answer("❌ Неверный номер. Попробуй снова:")
        return
    except Exception as e:
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML")
        await state.clear()
        return

    _clients[user_id] = {
        "client": client,
        "phone": phone,
        "phone_code_hash": sent.phone_code_hash,
    }

    await state.set_state(SessionGen.waiting_code)
    await message.answer(
        "✅ Код отправлен в Telegram!\n\n"
        "Введи код (только цифры, без пробелов):",
        parse_mode="HTML",
    )


@router.message(SessionGen.waiting_code)
async def handle_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "").replace("-", "")
    user_id = message.from_user.id
    data = _clients.get(user_id)

    if not data:
        await message.answer("❌ Сессия истекла. Начни заново: .gensession")
        await state.clear()
        return

    client: Client = data["client"]

    try:
        await client.sign_in(
            phone_number=data["phone"],
            phone_code_hash=data["phone_code_hash"],
            phone_code=code,
        )
    except (PhoneCodeInvalid, PhoneCodeExpired):
        await message.answer("❌ Неверный или просроченный код. Попробуй снова:")
        return
    except SessionPasswordNeeded:
        await state.set_state(SessionGen.waiting_2fa)
        await message.answer("🔐 На аккаунте включён пароль 2FA. Введи его:")
        return
    except Exception as e:
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML")
        await state.clear()
        _clients.pop(user_id, None)
        return

    await _finish_session(message, state, client, user_id)


@router.message(SessionGen.waiting_2fa)
async def handle_2fa(message: Message, state: FSMContext):
    password = message.text.strip()
    user_id = message.from_user.id
    data = _clients.get(user_id)

    if not data:
        await message.answer("❌ Сессия истекла. Начни заново: .gensession")
        await state.clear()
        return

    client: Client = data["client"]

    try:
        await client.check_password(password)
    except Exception as e:
        await message.answer(f"❌ Неверный пароль: <code>{e}</code>\nПопробуй снова:", parse_mode="HTML")
        return

    await _finish_session(message, state, client, user_id)


async def _finish_session(message: Message, state: FSMContext, client: Client, user_id: int):
    try:
        session_string = await client.export_session_string()
        await client.disconnect()
    except Exception as e:
        await message.answer(f"❌ Не удалось экспортировать сессию: <code>{e}</code>", parse_mode="HTML")
        await state.clear()
        _clients.pop(user_id, None)
        return

    _clients.pop(user_id, None)
    await state.clear()

    await message.answer(
        "✅ <b>Сессия создана!</b>\n\n"
        "Скопируй строку ниже и добавь на Railway → Variables:\n"
        "<b>Name:</b> <code>USERBOT_SESSION</code>\n"
        "<b>Value:</b>",
        parse_mode="HTML",
    )
    # Отправляем строку отдельным сообщением — удобнее копировать
    await message.answer(f"<code>{session_string}</code>", parse_mode="HTML")
    await message.answer(
        "После добавления переменной Railway перезапустит бота автоматически. "
        "В логах появится:\n<code>Userbot запущен: @твой_username</code>",
        parse_mode="HTML",
    )
