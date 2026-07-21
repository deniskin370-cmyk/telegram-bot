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
    await callback.message.edit_text(
        "🔑 <b>Введи ключ активации</b>\n\n"
        "Отправь ключ в следующем сообщении.\n"
        "Ключ выдаётся администратором бота.",
        reply_markup=back_button("chat_settings"),
        parse_mode="HTML"
    )


@router.message(KeyState.waiting_for_key)
async def process_key(message: Message, state: FSMContext):
    await state.clear()
    key_text = message.text.strip()
    key_data = await get_key(key_text)

    if not key_data:
        await message.answer(
            "❌ <b>Ключ недействителен или уже использован.</b>\n\n"
            "Проверь правильность ключа и попробуй снова.\n"
            "Получи новый ключ у администратора.",
            reply_markup=back_button("chat_settings"),
            parse_mode="HTML"
        )
        return

    expires_at = key_data.get("expires_at")
    success = await activate_user(message.from_user.id, key_text, expires_at)

    if success:
        if expires_at:
            expire_text = f"до <code>{expires_at}</code>"
        else:
            expire_text = "навсегда"

        await message.answer(
            f"✅ <b>Бот успешно активирован!</b>\n\n"
            f"Твой ключ действует {expire_text}.\n\n"
            "Теперь все команды будут работать в твоих чатах.\n"
            "Не забудь подключить бота через <b>Автоматизацию чатов</b>!",
            reply_markup=back_button("chat_settings"),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Произошла ошибка при активации. Попробуй снова.",
            reply_markup=back_button("chat_settings"),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "key_status")
async def cb_key_status(callback: CallbackQuery):
    activated = await is_user_activated(callback.from_user.id)
    status = "✅ Активирован" if activated else "❌ Не активирован"
    await callback.answer(f"Статус: {status}", show_alert=True)
