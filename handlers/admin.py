import random
import string
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Filter

from database import (
    is_admin, add_admin, remove_admin, get_all_admins,
    create_key, get_all_keys
)
from keyboards import admin_panel_menu, key_duration_menu, back_button
from config import CREATOR_ID

router = Router()


class AdminFilter(Filter):
    async def __call__(self, event) -> bool:
        user_id = event.from_user.id if hasattr(event, 'from_user') else None
        return user_id is not None and await is_admin(user_id)


class AdminState(StatesGroup):
    waiting_for_admin_id = State()
    waiting_for_remove_admin_id = State()
    waiting_for_key_duration_choice = State()


def generate_key(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("⛔ У тебя нет доступа к панели администратора.", show_alert=True)
        return
    await callback.message.edit_text(
        "🔑 <b>Панель администратора</b>\n\n"
        "Выбери действие:",
        reply_markup=admin_panel_menu(),
        parse_mode="HTML"
    )


# ─── Создать ключ ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_create_key")
async def cb_create_key(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "⏳ <b>Выбери срок действия ключа</b>",
        reply_markup=key_duration_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("duration_"))
async def cb_key_duration(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    duration_map = {
        "duration_1d": ("1 день", timedelta(days=1)),
        "duration_7d": ("7 дней", timedelta(days=7)),
        "duration_30d": ("30 дней", timedelta(days=30)),
        "duration_forever": ("Навсегда", None),
    }
    label, delta = duration_map.get(callback.data, ("Навсегда", None))

    key = generate_key()
    expires_at = None
    if delta:
        expires_at = (datetime.now() + delta).strftime("%Y-%m-%d %H:%M:%S")

    success = await create_key(key, callback.from_user.id, expires_at)
    if success:
        expires_text = f"<code>{expires_at}</code>" if expires_at else "♾ Навсегда"
        await callback.message.edit_text(
            f"✅ <b>Ключ создан!</b>\n\n"
            f"🔑 Ключ: <code>{key}</code>\n"
            f"⏳ Срок действия: {label} ({expires_text})\n\n"
            "Скопируй и передай пользователю.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при создании ключа.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )


# ─── Список ключей ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_list_keys")
async def cb_list_keys(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    keys = await get_all_keys()
    if not keys:
        text = "📋 <b>Ключи не найдены.</b>"
    else:
        lines = ["📋 <b>Последние ключи:</b>\n"]
        for k in keys:
            status = "✅" if k["is_active"] else "❌"
            expires = k["expires_at"] or "навсегда"
            lines.append(
                f"{status} <code>{k['key']}</code>\n"
                f"   Истекает: {expires}\n"
                f"   Создан: {k['created_at']}\n"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )


# ─── Добавить администратора ──────────────────────────────────────────────────

@router.callback_query(F.data == "admin_add_admin")
async def cb_add_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await state.set_state(AdminState.waiting_for_admin_id)
    await callback.message.edit_text(
        "👤 <b>Добавить администратора</b>\n\n"
        "Отправь <b>Telegram ID</b> пользователя, которого хочешь сделать администратором.\n\n"
        "Как узнать ID: попроси пользователя написать боту /start и перешли ID.\n"
        "Или используй @userinfobot",
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_admin_id)
async def process_add_admin(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()
    try:
        new_admin_id = int(message.text.strip())
        username = f"User_{new_admin_id}"
        success = await add_admin(new_admin_id, username)
        if success:
            await message.answer(
                f"✅ Пользователь <code>{new_admin_id}</code> назначен администратором!",
                reply_markup=back_button("admin_panel"),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Не удалось добавить администратора.",
                reply_markup=back_button("admin_panel"),
                parse_mode="HTML"
            )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введи числовой Telegram ID.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )


# ─── Список администраторов ───────────────────────────────────────────────────

@router.callback_query(F.data == "admin_list_admins")
async def cb_list_admins(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    admins = await get_all_admins()
    if not admins:
        text = "👥 <b>Администраторы не найдены.</b>"
    else:
        lines = ["👥 <b>Список администраторов:</b>\n"]
        for a in admins:
            is_creator = "👑 " if a["user_id"] == CREATOR_ID else ""
            lines.append(
                f"{is_creator}<code>{a['user_id']}</code> — {a['username']}\n"
                f"   Добавлен: {a['added_at']}"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )


# ─── Удалить администратора ───────────────────────────────────────────────────

@router.callback_query(F.data == "admin_remove_admin")
async def cb_remove_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await state.set_state(AdminState.waiting_for_remove_admin_id)
    await callback.message.edit_text(
        "🗑 <b>Удалить администратора</b>\n\n"
        "Отправь <b>Telegram ID</b> администратора, которого хочешь снять с должности.",
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_remove_admin_id)
async def process_remove_admin(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()
    try:
        target_id = int(message.text.strip())
        if target_id == CREATOR_ID:
            await message.answer(
                "⛔ Нельзя снять создателя бота с прав администратора.",
                reply_markup=back_button("admin_panel"),
                parse_mode="HTML"
            )
            return
        success = await remove_admin(target_id)
        if success:
            await message.answer(
                f"✅ Пользователь <code>{target_id}</code> снят с прав администратора.",
                reply_markup=back_button("admin_panel"),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Не удалось снять администратора. Проверь ID.",
                reply_markup=back_button("admin_panel"),
                parse_mode="HTML"
            )
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Введи числовой Telegram ID.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
