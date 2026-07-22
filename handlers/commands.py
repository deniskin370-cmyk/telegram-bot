import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, ChatPermissions
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from database import is_user_activated, mute_user, unmute_user, is_muted, is_admin
from config import CREATOR_ID

router = Router()


def format_time(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} мин."
    elif minutes < 1440:
        return f"{minutes // 60} ч."
    else:
        return f"{minutes // 1440} д."


# ─── .spam ────────────────────────────────────────────────────────────────────

async def _do_spam(message: Message):
    if not await is_user_activated(message.from_user.id):
        await message.answer(
            "❌ <b>Бот не активирован!</b>\n\n"
            "Нажми <b>⚙️ Настройка чатов</b> и введи ключ.",
            parse_mode="HTML",
        )
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.reply(
            "❌ <b>Неверный формат!</b>\n"
            "Использование: <code>.spam [текст] [количество]</code>\n"
            "Пример: <code>.spam Привет! 5</code>",
            parse_mode="HTML",
        )
        return

    try:
        count = int(parts[-1])
    except ValueError:
        await message.reply("❌ <b>Количество должно быть числом!</b>", parse_mode="HTML")
        return

    spam_text = " ".join(parts[1:-1])
    if not spam_text:
        await message.reply("❌ <b>Укажи текст для спама!</b>", parse_mode="HTML")
        return

    count = max(1, min(count, 30))

    try:
        await message.delete()
    except Exception:
        pass

    try:
        notify = await message.answer("📨 <b>Начинаю спам...</b>", parse_mode="HTML")
        await asyncio.sleep(0.3)
        await notify.delete()
    except Exception:
        pass

    for i in range(count):
        try:
            await message.answer(spam_text)
            if i < count - 1:
                await asyncio.sleep(0.1)
        except Exception:
            break


# ─── .mute в группе ───────────────────────────────────────────────────────────

async def _do_mute_group(message: Message, minutes: int):
    if not message.reply_to_message:
        await message.reply(
            "❌ <b>Ответь на сообщение пользователя которого хочешь замутить!</b>",
            parse_mode="HTML",
        )
        return

    target_user = message.reply_to_message.from_user
    until_date = datetime.now() + timedelta(minutes=minutes)
    time_text = format_time(minutes)

    try:
        await message.chat.restrict(
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date,
        )
        # Удаляем сообщение на которое ответили + команду .mute
        for msg in (message.reply_to_message, message):
            try:
                await msg.delete()
            except Exception:
                pass
        await message.answer(
            f"🔇 <b>{target_user.mention_html()} замучен на {time_text}</b>\n"
            f"🕐 До: {until_date.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML",
        )
    except Exception as e:
        err = str(e)
        if "not enough rights" in err or "CHAT_ADMIN_REQUIRED" in err:
            await message.reply("❌ <b>У бота нет прав администратора в этой группе!</b>", parse_mode="HTML")
        else:
            await message.reply(f"❌ Ошибка: <code>{err}</code>", parse_mode="HTML")


# ─── .mute в ЛС (business mode) ──────────────────────────────────────────────

async def _do_mute_dm(message: Message, minutes: int):
    target_id = message.chat.id
    until_date = datetime.now() + timedelta(minutes=minutes)
    time_text = format_time(minutes)

    success = await mute_user(target_id, until_date)

    try:
        await message.delete()
    except Exception:
        pass

    if success:
        await message.answer(
            f"🔇 <b>Пользователь замучен на {time_text}</b>\n"
            f"🕐 До: {until_date.strftime('%d.%m.%Y %H:%M')}\n"
            "Его сообщения будут автоматически удаляться (Connected Bots) "
            "или получат авто-ответ об отклонении (Автоматизация чатов).",
            parse_mode="HTML",
        )
    else:
        await message.answer("❌ Не удалось замутить пользователя.")


# ─── .unmute в ЛС (business mode) ────────────────────────────────────────────

async def _do_unmute_dm(message: Message):
    target_id = message.chat.id

    try:
        await message.delete()
    except Exception:
        pass

    success = await unmute_user(target_id)
    if success:
        await message.answer("🔊 <b>Мут снят.</b> Пользователь снова может писать.", parse_mode="HTML")
    else:
        await message.answer("❌ Не удалось снять мут.")


# ─── Общий разбор .mute [число] ───────────────────────────────────────────────

async def _do_mute(message: Message):
    if not await is_user_activated(message.from_user.id):
        await message.answer(
            "❌ <b>Бот не активирован!</b>\n\n"
            "Нажми <b>⚙️ Настройка чатов</b> и введи ключ.",
            parse_mode="HTML",
        )
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "❌ <b>Укажи время в минутах!</b>\n"
            "Пример: <code>.mute 10</code> — замутить на 10 минут",
            parse_mode="HTML",
        )
        return

    try:
        minutes = int(parts[1])
        if minutes < 1:
            raise ValueError
    except ValueError:
        await message.reply(
            "❌ <b>Укажи целое число минут!</b>\n"
            "Пример: <code>.mute 10</code>",
            parse_mode="HTML",
        )
        return

    if message.chat.type in ("group", "supergroup"):
        await _do_mute_group(message, minutes)
    else:
        await _do_mute_dm(message, minutes)


async def _do_unmute(message: Message):
    if not await is_user_activated(message.from_user.id):
        await message.answer("❌ <b>Бот не активирован!</b>", parse_mode="HTML")
        return

    if message.chat.type in ("group", "supergroup"):
        await message.reply("❌ Команда .unmute работает только в ЛС.")
        return

    await _do_unmute_dm(message)


# ─── .info ────────────────────────────────────────────────────────────────────

async def _do_info(message: Message):
    if not await is_user_activated(message.from_user.id):
        await message.answer("❌ <b>Бот не активирован!</b>", parse_mode="HTML")
        return

    # Определяем цель: reply → тот пользователь, иначе собеседник (ЛС) или отправитель (группа)
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        target_id = target.id
    elif message.chat.type == "private":
        target = message.from_user
        target_id = target.id
    else:
        # В группе без reply — показываем себя
        target = message.from_user
        target_id = target.id

    # Удаляем команду из чата
    try:
        await message.delete()
    except Exception:
        pass

    # Telegram-профиль через get_chat (получаем bio, фото)
    bio_text = "—"
    photos_count = 0
    try:
        chat_info = await message.bot.get_chat(target_id)
        if chat_info.bio:
            bio_text = chat_info.bio
        photos = await message.bot.get_user_profile_photos(target_id, limit=1)
        photos_count = photos.total_count
    except Exception:
        pass

    # База бота
    muted = await is_muted(target_id)
    activated = await is_user_activated(target_id)
    admin = await is_admin(target_id)

    # Собираем имя
    full_name = target.full_name or "—"
    username = f"@{target.username}" if target.username else "—"
    premium = "✅ Да" if getattr(target, "is_premium", False) else "❌ Нет"
    is_bot_flag = "🤖 Да" if target.is_bot else "👤 Нет"
    lang = target.language_code or "—"

    text = (
        f"🔍 <b>Информация о пользователе</b>\n"
        f"{'─' * 28}\n"
        f"👤 <b>Имя:</b> {full_name}\n"
        f"🔗 <b>Username:</b> {username}\n"
        f"🆔 <b>ID:</b> <code>{target_id}</code>\n"
        f"🤖 <b>Бот:</b> {is_bot_flag}\n"
        f"⭐ <b>Premium:</b> {premium}\n"
        f"🌐 <b>Язык:</b> {lang}\n"
        f"📷 <b>Фото:</b> {photos_count} шт.\n"
        f"📝 <b>Bio:</b> {bio_text}\n"
        f"{'─' * 28}\n"
        f"<b>Статус в боте:</b>\n"
        f"🔇 <b>Мут:</b> {'да' if muted else 'нет'}\n"
        f"🔑 <b>Активирован:</b> {'да' if activated else 'нет'}\n"
        f"🛡 <b>Администратор:</b> {'да' if admin else 'нет'}\n"
    )

    # Отправляем результат в личку с ботом тому, кто вызвал команду
    try:
        await message.bot.send_message(
            chat_id=message.from_user.id,
            text=text,
            parse_mode="HTML",
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        # Если бот заблокирован — отправляем прямо в чат (исчезнет через 10 сек)
        try:
            notice = await message.answer(text, parse_mode="HTML")
            await asyncio.sleep(15)
            await notice.delete()
        except Exception:
            pass


# ─── Обычные сообщения (в группах и личке) ────────────────────────────────────

@router.message(F.text.startswith(".spam"))
async def cmd_spam(message: Message):
    await _do_spam(message)


@router.message(F.text.startswith(".mute"))
async def cmd_mute(message: Message):
    await _do_mute(message)


@router.message(F.text.startswith(".unmute"))
async def cmd_unmute(message: Message):
    await _do_unmute(message)


@router.message(F.text.startswith(".info"))
async def cmd_info(message: Message):
    await _do_info(message)


# ─── Business-сообщения ───────────────────────────────────────────────────────

@router.business_message(F.text.startswith(".spam"))
async def cmd_spam_business(message: Message):
    await _do_spam(message)


@router.business_message(F.text.startswith(".unmute"))
async def cmd_unmute_business(message: Message):
    await _do_unmute(message)


@router.business_message(F.text.startswith(".mute"))
async def cmd_mute_business(message: Message):
    await _do_mute(message)


@router.business_message(F.text.startswith(".info"))
async def cmd_info_business(message: Message):
    await _do_info(message)


