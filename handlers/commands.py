import asyncio
import re
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, ChatPermissions

from database import is_user_activated, mute_user, is_muted

router = Router()


def parse_duration(duration_str: str) -> int | None:
    match = re.fullmatch(r"(\d+)(m|h|d)", duration_str.lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {"m": 60, "h": 3600, "d": 86400}
    return value * multipliers[unit]


def format_time(seconds: int) -> str:
    if seconds < 3600:
        mins = seconds // 60
        return f"{mins} мин."
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} ч."
    else:
        days = seconds // 86400
        return f"{days} д."


# ─── .spam ────────────────────────────────────────────────────────────────────

async def _do_spam(message: Message):
    if not await is_user_activated(message.from_user.id):
        await message.answer(
            "❌ <b>Бот не активирован!</b>\n\n"
            "Введи ключ активации в разделе <b>⚙️ Настройка чатов</b>."
        )
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.reply(
            "❌ <b>Неверный формат!</b>\n"
            "Использование: <code>.spam [текст] [количество]</code>\n"
            "Пример: <code>.spam Привет! 5</code>"
        )
        return

    try:
        count = int(parts[-1])
    except ValueError:
        await message.reply(
            "❌ <b>Количество должно быть числом!</b>\n"
            "Пример: <code>.spam Привет! 5</code>"
        )
        return

    spam_text = " ".join(parts[1:-1])
    if not spam_text:
        await message.reply("❌ <b>Укажи текст для спама!</b>")
        return

    if count < 1:
        await message.reply("❌ Количество должно быть не менее 1.")
        return

    if count > 30:
        count = 30

    # Удаляем команду и пишем уведомление
    try:
        await message.delete()
    except Exception:
        pass

    try:
        notify = await message.answer("📨 <b>Начинаю спам...</b>")
    except Exception:
        notify = None

    # Небольшая пауза чтобы уведомление успело отправиться
    await asyncio.sleep(0.3)

    # Удаляем уведомление и спамим
    if notify:
        try:
            await notify.delete()
        except Exception:
            pass

    for i in range(count):
        try:
            await message.answer(spam_text)
            if i < count - 1:
                await asyncio.sleep(0.1)  # быстрый спам
        except Exception:
            break


# ─── .mute в группах ──────────────────────────────────────────────────────────

async def _do_mute_group(message: Message):
    """Мут в обычной группе через ограничение прав."""
    if not message.reply_to_message:
        await message.reply(
            "❌ <b>Ответь на сообщение пользователя, которого хочешь замутить!</b>\n"
            "Пример: ответь на сообщение → <code>.mute 10m</code>"
        )
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "❌ <b>Укажи время мута!</b>\n"
            "Форматы: <code>5m</code> (мин), <code>1h</code> (час), <code>2d</code> (дни)\n"
            "Пример: <code>.mute 10m</code>"
        )
        return

    seconds = parse_duration(parts[1])
    if seconds is None:
        await message.reply(
            "❌ <b>Неверный формат времени!</b>\n"
            "Форматы: <code>5m</code> (мин), <code>1h</code> (час), <code>2d</code> (дни)"
        )
        return

    target_user = message.reply_to_message.from_user
    until_date = datetime.now() + timedelta(seconds=seconds)
    time_text = format_time(seconds)

    try:
        await message.chat.restrict(
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )

        # Удаляем команду
        try:
            await message.delete()
        except Exception:
            pass

        await message.answer(
            f"🔇 <b>{target_user.mention_html()} замучен</b>\n"
            f"⏳ Срок: {time_text}\n"
            f"🕐 До: {until_date.strftime('%d.%m.%Y %H:%M')}"
        )
    except Exception as e:
        err = str(e)
        if "not enough rights" in err or "CHAT_ADMIN_REQUIRED" in err:
            await message.reply(
                "❌ <b>У бота недостаточно прав!</b>\n"
                "Назначь бота администратором группы с правом ограничивать участников."
            )
        else:
            await message.reply(f"❌ Не удалось замутить пользователя.\n<code>{err}</code>")


# ─── .mute в ЛС (business mode) ──────────────────────────────────────────────

async def _do_mute_dm(message: Message):
    """
    Мут в личных сообщениях через business mode.
    Замучивает собеседника: его следующие сообщения будут автоматически удаляться.
    Использование: .mute 10m (в диалоге с нужным человеком)
    """
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "❌ <b>Укажи время мута!</b>\n"
            "Форматы: <code>5m</code> (мин), <code>1h</code> (час), <code>2d</code> (дни)\n"
            "Пример: <code>.mute 10m</code>"
        )
        return

    seconds = parse_duration(parts[1])
    if seconds is None:
        await message.reply(
            "❌ <b>Неверный формат времени!</b>\n"
            "Форматы: <code>5m</code> (мин), <code>1h</code> (час), <code>2d</code> (дни)"
        )
        return

    # В business DM: chat.id — это ID собеседника
    target_id = message.chat.id
    until_date = datetime.now() + timedelta(seconds=seconds)
    time_text = format_time(seconds)

    success = await mute_user(target_id, until_date)

    # Удаляем команду
    try:
        await message.delete()
    except Exception:
        pass

    if success:
        await message.answer(
            f"🔇 <b>Пользователь замучен на {time_text}</b>\n"
            f"🕐 До: {until_date.strftime('%d.%m.%Y %H:%M')}\n"
            "Его сообщения будут автоматически удаляться."
        )
    else:
        await message.answer("❌ Не удалось замутить пользователя.")


# ─── Общая точка входа для .mute ─────────────────────────────────────────────

async def _do_mute(message: Message):
    if not await is_user_activated(message.from_user.id):
        await message.answer(
            "❌ <b>Бот не активирован!</b>\n\n"
            "Введи ключ активации в разделе <b>⚙️ Настройка чатов</b>."
        )
        return

    if message.chat.type in ("group", "supergroup"):
        await _do_mute_group(message)
    else:
        # ЛС или business DM
        await _do_mute_dm(message)


# ─── Обычные сообщения ────────────────────────────────────────────────────────

@router.message(F.text.startswith(".spam"))
async def cmd_spam(message: Message):
    await _do_spam(message)


@router.message(F.text.startswith(".mute"))
async def cmd_mute(message: Message):
    await _do_mute(message)


# ─── Business-сообщения (через «Автоматизацию чатов») ────────────────────────

@router.business_message(F.text.startswith(".spam"))
async def cmd_spam_business(message: Message):
    await _do_spam(message)


@router.business_message(F.text.startswith(".mute"))
async def cmd_mute_business(message: Message):
    await _do_mute(message)
