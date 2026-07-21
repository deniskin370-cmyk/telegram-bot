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
from keyboards import admin_panel_menu, key_unit_menu, key_amount_menu, back_button
from config import CREATOR_ID

router = Router()


class AdminFilter(Filter):
    async def __call__(self, event) -> bool:
        user_id = event.from_user.id if hasattr(event, 'from_user') else None
        return user_id is not None and await is_admin(user_id)


class AdminState(StatesGroup):
    waiting_for_admin_id = State()
    waiting_for_remove_admin_id = State()


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


# ─── Создать ключ: Шаг 1 — выбор единицы ─────────────────────────────────────

@router.callback_query(F.data == "admin_create_key")
async def cb_create_key(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "⏳ <b>Создание ключа — Шаг 1</b>\n\n"
        "Выбери единицу времени для срока действия ключа:",
        reply_markup=key_unit_menu(),
        parse_mode="HTML"
    )


# ─── Создать ключ: Шаг 2 — выбор количества ──────────────────────────────────

@router.callback_query(F.data.startswith("kunit_"))
async def cb_key_unit(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    unit = callback.data.replace("kunit_", "")  # hours / days / months / forever

    if unit == "forever":
        # Сразу создаём ключ навсегда
        key = generate_key()
        success = await create_key(key, callback.from_user.id, None)
        if success:
            await callback.message.edit_text(
                f"✅ <b>Ключ создан!</b>\n\n"
                f"🔑 Ключ: <code>{key}</code>\n"
                f"⏳ Срок действия: <b>♾ Навсегда</b>\n"
                f"👤 Для: 1 пользователя\n\n"
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
        return

    unit_labels = {"hours": "часы", "days": "дни", "months": "месяцы"}
    await callback.message.edit_text(
        f"⏳ <b>Создание ключа — Шаг 2</b>\n\n"
        f"Единица: <b>{unit_labels.get(unit, unit)}</b>\n"
        "Выбери количество:",
        reply_markup=key_amount_menu(unit),
        parse_mode="HTML"
    )


# ─── Создать ключ: финал — создание после выбора количества ──────────────────

@router.callback_query(F.data.startswith("kamount_"))
async def cb_key_amount(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    # kamount_hours_3 / kamount_days_7 / kamount_months_1
    parts = callback.data.split("_")  # ['kamount', 'hours', '3']
    if len(parts) != 3:
        return await callback.answer("❌ Ошибка формата.", show_alert=True)

    unit = parts[1]
    try:
        amount = int(parts[2])
    except ValueError:
        return await callback.answer("❌ Ошибка формата.", show_alert=True)

    unit_seconds = {"hours": 3600, "days": 86400, "months": 2592000}  # month = 30d
    seconds = amount * unit_seconds[unit]
    expires_at = (datetime.now() + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")

    unit_labels = {
        "hours": ("ч", "час", "часа", "часов"),
        "days": ("д", "день", "дня", "дней"),
        "months": ("мес", "месяц", "месяца", "месяцев"),
    }
    short, f1, f2, f5 = unit_labels[unit]

    if amount == 1:
        label = f"{amount} {f1}"
    elif 2 <= amount <= 4:
        label = f"{amount} {f2}"
    else:
        label = f"{amount} {f5}"

    key = generate_key()
    success = await create_key(key, callback.from_user.id, expires_at)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Ключ создан!</b>\n\n"
            f"🔑 Ключ: <code>{key}</code>\n"
            f"⏳ Срок действия: <b>{label}</b>\n"
            f"📅 Истекает: <code>{expires_at}</code>\n"
            f"👤 Для: 1 пользователя\n\n"
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
        lines = ["📋 <b>Последние ключи (до 50):</b>\n"]
        for k in keys:
            status = "✅" if k["is_active"] else "❌"
            used = f"👤 {k['used_by']}" if k.get("used_by") else "🔓 Свободен"
            exp = k.get("expires_at") or "♾"
            lines.append(
                f"{status} <code>{k['key']}</code>\n"
                f"   {used} | до {exp}\n"
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
        "<i>ID можно узнать через @userinfobot</i>",
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
        target_id = int(message.text.strip())
        success = await add_admin(target_id)
        if success:
            await message.answer(
                f"✅ Пользователь <code>{target_id}</code> назначен администратором.",
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
        lines = ["👥 <b>Администраторы:</b>\n"]
        for a in admins:
            crown = "👑 " if a["user_id"] == CREATOR_ID else ""
            lines.append(f"{crown}<code>{a['user_id']}</code> — {a.get('username') or '—'}")
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
