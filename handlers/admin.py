import random
import string
import aiohttp
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Filter

from database import (
    is_admin, add_admin, remove_admin, get_all_admins,
    create_key, get_all_keys, get_stats, deactivate_key
)
from keyboards import admin_panel_menu, key_unit_menu, key_amount_menu, back_button
from config import CREATOR_ID, BOT_TOKEN

router = Router()


class AdminFilter(Filter):
    async def __call__(self, event) -> bool:
        user_id = event.from_user.id if hasattr(event, 'from_user') else None
        return user_id is not None and await is_admin(user_id)


class AdminState(StatesGroup):
    waiting_for_admin_input = State()
    waiting_for_remove_admin_input = State()
    waiting_for_deactivate_key = State()
    waiting_for_gift_user = State()
    waiting_for_gift_stars = State()


def generate_key(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


async def resolve_user(bot: Bot, text: str) -> tuple[int | None, str]:
    """
    Принимает @username или числовой ID.
    Возвращает (user_id, подпись) или (None, текст_ошибки).
    """
    text = text.strip()
    # Числовой ID
    clean = text.lstrip('@')
    if clean.lstrip('-').isdigit():
        return int(clean), f"<code>{clean}</code>"
    # Username
    username = clean if text.startswith('@') else text
    try:
        chat = await bot.get_chat(f"@{username}")
        return chat.id, f"@{username}"
    except Exception as e:
        return None, str(e)


# ─── Панель администратора ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "🔑 <b>Панель администратора</b>\n\nВыбери действие:",
        reply_markup=admin_panel_menu(is_creator=callback.from_user.id == CREATOR_ID),
        parse_mode="HTML"
    )


# ─── Статистика ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def cb_stats(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    s = await get_stats()
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{s['total_users']}</b>\n"
        f"✅ Активных пользователей: <b>{s['active_users']}</b>\n"
        f"👮 Администраторов: <b>{s['total_admins']}</b>\n\n"
        f"🔑 Всего ключей создано: <b>{s['total_keys']}</b>\n"
        f"🔓 Свободных ключей: <b>{s['active_keys']}</b>\n"
        f"🔒 Использованных ключей: <b>{s['used_keys']}</b>\n\n"
        f"🔇 Замучено пользователей: <b>{s['muted_count']}</b>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )


# ─── Создать ключ: Шаг 1 ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_create_key")
async def cb_create_key(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await callback.message.edit_text(
        "⏳ <b>Создание ключа — Шаг 1</b>\n\nВыбери единицу времени:",
        reply_markup=key_unit_menu(),
        parse_mode="HTML"
    )


# ─── Создать ключ: Шаг 2 ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kunit_"))
async def cb_key_unit(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    unit = callback.data.replace("kunit_", "")

    if unit == "forever":
        key = generate_key()
        success = await create_key(key, callback.from_user.id, None)
        if success:
            await callback.message.edit_text(
                f"✅ <b>Ключ создан!</b>\n\n"
                f"🔑 Ключ: <code>{key}</code>\n"
                f"⏳ Срок: <b>♾ Навсегда</b>\n\n"
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
        f"Единица: <b>{unit_labels.get(unit, unit)}</b>\nВыбери количество:",
        reply_markup=key_amount_menu(unit),
        parse_mode="HTML"
    )


# ─── Создать ключ: финал ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kamount_"))
async def cb_key_amount(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    parts = callback.data.split("_")
    if len(parts) != 3:
        return await callback.answer("❌ Ошибка формата.", show_alert=True)

    unit = parts[1]
    try:
        amount = int(parts[2])
    except ValueError:
        return await callback.answer("❌ Ошибка формата.", show_alert=True)

    unit_seconds = {"hours": 3600, "days": 86400, "months": 2592000}
    seconds = amount * unit_seconds[unit]
    expires_at = (datetime.now() + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")

    unit_labels = {
        "hours": ("час", "часа", "часов"),
        "days": ("день", "дня", "дней"),
        "months": ("месяц", "месяца", "месяцев"),
    }
    f1, f2, f5 = unit_labels[unit]
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
            f"⏳ Срок: <b>{label}</b>\n"
            f"📅 Истекает: <code>{expires_at}</code>\n\n"
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


# ─── Отправить подарок с баланса бота (только CREATOR_ID) ────────────────────

async def _get_gift_id(star_count: int) -> str | None:
    """Ищет gift_id по количеству звёзд через Telegram API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getAvailableGifts"
            ) as resp:
                data = await resp.json()
        if not data.get("ok"):
            return None
        for gift in data["result"]["gifts"]:
            if gift["star_count"] == star_count:
                return gift["id"]
    except Exception:
        pass
    return None


async def _send_gift(user_id: int, gift_id: str) -> tuple[bool, str]:
    """Отправляет подарок пользователю. Возвращает (ok, error_text)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendGift",
                json={"user_id": user_id, "gift_id": gift_id},
            ) as resp:
                data = await resp.json()
        if data.get("ok"):
            return True, ""
        return False, data.get("description", "Unknown error")
    except Exception as e:
        return False, str(e)


@router.callback_query(F.data == "admin_send_gift")
async def cb_send_gift(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != CREATOR_ID:
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await state.set_state(AdminState.waiting_for_gift_user)
    await callback.message.edit_text(
        "⭐️ <b>Отправить подарок пользователю</b>\n\n"
        "Отправь <b>@username</b> или <b>Telegram ID</b> получателя:",
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML",
    )


@router.message(AdminState.waiting_for_gift_user)
async def process_gift_user(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != CREATOR_ID:
        await state.clear()
        return

    user_id, label = await resolve_user(bot, message.text.strip())
    if user_id is None:
        await message.answer(
            f"❌ Не удалось найти пользователя: <code>{label}</code>\n\n"
            "Введи корректный @username или числовой ID.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML",
        )
        return

    await state.update_data(gift_target_id=user_id, gift_target_label=label)
    await state.set_state(AdminState.waiting_for_gift_stars)
    await message.answer(
        f"👤 Получатель: {label}\n\n"
        "Введи количество ⭐️ звёзд для подарка <b>(от 1 до 100000)</b>:",
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML",
    )


@router.message(AdminState.waiting_for_gift_stars)
async def process_gift_stars(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id != CREATOR_ID:
        await state.clear()
        return

    try:
        stars = int(message.text.strip())
        if not (1 <= stars <= 100000):
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Введи целое число от 1 до 100000.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    target_id = data.get("gift_target_id")
    label = data.get("gift_target_label", str(target_id))
    await state.clear()

    await message.answer(f"⏳ Ищу подарок на {stars} ⭐️ и отправляю...")

    gift_id = await _get_gift_id(stars)
    if not gift_id:
        await message.answer(
            f"❌ <b>Подарок на {stars} ⭐️ не найден в Telegram.</b>\n"
            "Такого подарка нет в магазине. Попробуй другое количество.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML",
        )
        return

    ok, err = await _send_gift(target_id, gift_id)
    if ok:
        await message.answer(
            f"✅ <b>Подарок отправлен!</b>\n\n"
            f"👤 Получатель: {label}\n"
            f"🎁 Подарок: {stars} ⭐️",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❌ <b>Не удалось отправить подарок</b>\n\n"
            f"Ошибка: <code>{err}</code>\n\n"
            "Убедись, что на балансе бота достаточно звёзд.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML",
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


# ─── Обнулить ключ ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_deactivate_key")
async def cb_deactivate_key(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await state.set_state(AdminState.waiting_for_deactivate_key)
    await callback.message.edit_text(
        "🚫 <b>Обнулить ключ</b>\n\n"
        "Отправь ключ, который хочешь деактивировать.",
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_deactivate_key)
async def process_deactivate_key(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()
    key_text = message.text.strip()
    success = await deactivate_key(key_text)
    if success:
        await message.answer(
            f"✅ Ключ <code>{key_text}</code> деактивирован.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Ключ не найден. Проверь правильность.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )


# ─── Добавить администратора (по @username или ID) ────────────────────────────

@router.callback_query(F.data == "admin_add_admin")
async def cb_add_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await state.set_state(AdminState.waiting_for_admin_input)
    await callback.message.edit_text(
        "👤 <b>Добавить администратора</b>\n\n"
        "Отправь <b>@username</b> или <b>Telegram ID</b> пользователя:",
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_admin_input)
async def process_add_admin(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()

    user_id, label = await resolve_user(bot, message.text.strip())
    if user_id is None:
        await message.answer(
            f"❌ Не удалось найти пользователя: <code>{label}</code>\n"
            "Введи корректный @username или числовой ID.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
        return

    success = await add_admin(user_id)
    if success:
        await message.answer(
            f"✅ Пользователь {label} назначен администратором.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Не удалось добавить администратора.",
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


# ─── Удалить администратора (по @username или ID) ─────────────────────────────

@router.callback_query(F.data == "admin_remove_admin")
async def cb_remove_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)
    await state.set_state(AdminState.waiting_for_remove_admin_input)
    await callback.message.edit_text(
        "🗑 <b>Удалить администратора</b>\n\n"
        "Отправь <b>@username</b> или <b>Telegram ID</b> администратора:",
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )


@router.message(AdminState.waiting_for_remove_admin_input)
async def process_remove_admin(message: Message, state: FSMContext, bot: Bot):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return
    await state.clear()

    user_id, label = await resolve_user(bot, message.text.strip())
    if user_id is None:
        await message.answer(
            f"❌ Не удалось найти пользователя: <code>{label}</code>\n"
            "Введи корректный @username или числовой ID.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
        return

    if user_id == CREATOR_ID:
        await message.answer(
            "⛔ Нельзя снять создателя бота.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
        return

    success = await remove_admin(user_id)
    if success:
        await message.answer(
            f"✅ Пользователь {label} снят с прав администратора.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ Не удалось снять администратора {label}. Проверь корректность.",
            reply_markup=back_button("admin_panel"),
            parse_mode="HTML"
        )
