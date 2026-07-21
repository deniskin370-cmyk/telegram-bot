from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_key, activate_user, is_user_activated
from keyboards import chat_settings_menu, back_button

router = Router()


class KeyState(StatesGroup):
    waiting_for_key = State()


@router.callback_query(F.data == "enter_key")
async def cb_enter_key(callback: CallbackQuery, state: FSMContext):
    await state.set_state(KeyState.waiting_for_key)
    await callback.message.answer(
        "🔑 <b>Введи ключ активации</b>\n\n"
        "Отправь ключ следующим сообщением.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(KeyState.waiting_for_key)
async def process_key(message: Message, state: FSMContext):
    await state.clear()
    key_text = message.text.strip()
    key_data = await get_key(key_text)

    if not key_data:
        await message.answer(
            "❌ <b>Ключ недействителен или уже использован.</b>\n\n"
            "Проверь правильность ключа или купи новый через <b>🛒 Купить ключ</b>.",
            parse_mode="HTML"
        )
        return

    expires_at = key_data.get("expires_at")
    success = await activate_user(message.from_user.id, key_text, expires_at)

    if success:
        expire_text = f"до <code>{expires_at}</code>" if expires_at else "навсегда"
        await message.answer(
            f"✅ <b>Бот успешно активирован!</b>\n\n"
            f"Ключ действует {expire_text}.\n\n"
            "Не забудь подключить бота через <b>Автоматизацию чатов</b>!",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка при активации. Попробуй снова.")


@router.callback_query(F.data == "key_status")
async def cb_key_status(callback: CallbackQuery):
    activated = await is_user_activated(callback.from_user.id)
    status = "✅ Активирован" if activated else "❌ Не активирован"
    await callback.answer(f"Статус: {status}", show_alert=True)
