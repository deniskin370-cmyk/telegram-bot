import asyncio
import re
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, ChatPermissions

from database import is_user_activated

router = Router()


def parse_duration(duration_str: str) -> int | None:
    """Parse duration string like '10m', '1h', '2d' into seconds."""
    match = re.fullmatch(r"(\d+)(m|h|d)", duration_str.lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {"m": 60, "h": 3600, "d": 86400}
    return value * multipliers[unit]


@router.message(F.text.startswith(".spam"))
async def cmd_spam(message: Message):
    # Проверяем активацию
    if not await is_user_activated(message.from_user.id):
        await message.answer(
            "❌ <b>Бот не активирован!</b>\n\n"
            "Введи ключ активации в разделе <b>⚙️ Настройка чатов</b>.",
            parse_mode="HTML"
        )
        return

    parts = message.text.split()
    # Формат: .spam текст количество
    # Если частей меньше 3 — ошибка
    if len(parts) < 3:
        await message.reply(
            "❌ <b>Неверный формат!</b>\n"
            "Использование: <code>.spam [текст] [количество]</code>\n"
            "Пример: <code>.spam Привет! 5</code>",
            parse_mode="HTML"
        )
        return

    # Количество — последний аргумент
    try:
        count = int(parts[-1])
    except ValueError:
        await message.reply(
            "❌ <b>Количество должно быть числом!</b>\n"
            "Пример: <code>.spam Привет! 5</code>",
            parse_mode="HTML"
        )
        return

    # Текст — всё между командой и количеством
    spam_text = " ".join(parts[1:-1])

    if not spam_text:
        await message.reply(
            "❌ <b>Укажи текст для спама!</b>\n"
            "Пример: <code>.spam Привет! 5</code>",
            parse_mode="HTML"
        )
        return

    if count < 1:
        await message.reply("❌ Количество должно быть не менее 1.")
        return

    if count > 30:
        await message.reply(
            "⚠️ <b>Максимальное количество сообщений — 30!</b>\n"
            "Значение будет ограничено до 30.",
            parse_mode="HTML"
        )
        count = 30

    # Удаляем команду
    try:
        await message.delete()
    except Exception:
        pass

    # Спамим с небольшой задержкой
    for i in range(count):
        try:
            await message.answer(spam_text)
            if i < count - 1:
                await asyncio.sleep(0.5)  # Задержка 0.5 сек между сообщениями
        except Exception:
            break


@router.message(F.text.startswith(".mute"))
async def cmd_mute(message: Message):
    # Проверяем активацию
    if not await is_user_activated(message.from_user.id):
        await message.answer(
            "❌ <b>Бот не активирован!</b>\n\n"
            "Введи ключ активации в разделе <b>⚙️ Настройка чатов</b>.",
            parse_mode="HTML"
        )
        return

    # Команда должна быть в группе/супергруппе
    if message.chat.type not in ("group", "supergroup"):
        await message.reply(
            "❌ <b>Команда .mute работает только в группах!</b>",
            parse_mode="HTML"
        )
        return

    # Должен быть ответ на сообщение пользователя
    if not message.reply_to_message:
        await message.reply(
            "❌ <b>Ответь на сообщение пользователя, которого хочешь замутить!</b>\n"
            "Пример: ответь на сообщение и напиши <code>.mute 10m</code>",
            parse_mode="HTML"
        )
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "❌ <b>Укажи время мута!</b>\n"
            "Форматы: <code>5m</code> (мин), <code>1h</code> (час), <code>2d</code> (дни)\n"
            "Пример: <code>.mute 10m</code>",
            parse_mode="HTML"
        )
        return

    duration_str = parts[1]
    seconds = parse_duration(duration_str)

    if seconds is None:
        await message.reply(
            "❌ <b>Неверный формат времени!</b>\n"
            "Форматы: <code>5m</code> (мин), <code>1h</code> (час), <code>2d</code> (дни)\n"
            "Пример: <code>.mute 10m</code>",
            parse_mode="HTML"
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

        # Человекочитаемое время
        if seconds < 3600:
            time_text = f"{seconds // 60} мин."
        elif seconds < 86400:
            time_text = f"{seconds // 3600} ч."
        else:
            time_text = f"{seconds // 86400} д."

        await message.reply(
            f"🔇 <b>Пользователь {target_user.mention_html()} замучен</b>\n"
            f"⏳ Срок: {time_text}\n"
            f"🕐 До: {until_date.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
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
                "Назначь бота администратором группы с правом ограничивать участников.",
                parse_mode="HTML"
            )
        else:
            await message.reply(
                f"❌ Не удалось замутить пользователя.\n<code>{err}</code>",
                parse_mode="HTML"
            )
