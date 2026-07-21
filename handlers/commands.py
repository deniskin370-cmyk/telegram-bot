import asyncio
import re
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, ChatPermissions

from database import is_user_activated

router = Router()


def parse_duration(duration_str: str) -> int | None:
    match = re.fullmatch(r"(\d+)(m|h|d)", duration_str.lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {"m": 60, "h": 3600, "d": 86400}
    return value * multipliers[unit]


# ─── Общая логика ─────────────────────────────────────────────────────────────

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
        await message.reply("⚠️ <b>Максимум 30 сообщений.</b> Ограничиваю до 30.")
        count = 30

    try:
        await message.delete()
    except Exception:
        pass

    for i in range(count):
        try:
            await message.answer(spam_text)
            if i < count - 1:
                await asyncio.sleep(0.5)
        except Exception:
            break


async def _do_mute(message: Message):
    if not await is_user_activated(message.from_user.id):
        await message.answer(
            "❌ <b>Бот не активирован!</b>\n\n"
            "Введи ключ активации в разделе <b>⚙️ Настройка чатов</b>."
        )
        return

    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ <b>Команда .mute работает только в группах!</b>")
        return

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

    try:
        await message.chat.restrict(
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )

        if seconds < 3600:
            time_text = f"{seconds // 60} мин."
        elif seconds < 86400:
            time_text = f"{seconds // 3600} ч."
        else:
            time_text = f"{seconds // 86400} д."

        await message.reply(
            f"🔇 <b>{target_user.mention_html()} замучен</b>\n"
            f"⏳ Срок: {time_text}\n"
            f"🕐 До: {until_date.strftime('%d.%m.%Y %H:%M')}"
        )
        try:
            await message.delete()
        except Exception:
            pass
    except Exception as e:
        err = str(e)
        if "not enough rights" in err or "CHAT_ADMIN_REQUIRED" in err:
            await message.reply(
                "❌ <b>У бота недостаточно прав!</b>\n"
                "Назначь бота администратором группы с правом ограничивать участников."
            )
        else:
            await message.reply(f"❌ Не удалось замутить пользователя.\n<code>{err}</code>")


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
