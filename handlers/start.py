from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from database import is_admin, is_user_activated, get_activation
from keyboards import main_menu, back_button, chat_settings_menu
from config import CREATOR_ID

router = Router()

TUTORIAL_TEXT = """
📲 <b>Как подключить бота к своим чатам</b>

Чтобы бот работал во всех твоих личных сообщениях, выполни следующие шаги:

<b>Шаг 1.</b> Открой <b>Настройки</b> → <b>Мой профиль</b>
<b>Шаг 2.</b> Нажми <b>Изменить</b>
<b>Шаг 3.</b> Выбери <b>Автоматизация чатов</b>
<b>Шаг 4.</b> Впиши <code>@wertysrak_bot</code>

✅ После подключения бот начнёт работать во всех твоих ЛС!

⚠️ <b>Важно:</b> для работы бота в чатах необходим активный ключ.
Перейди в <b>⚙️ Настройка чатов</b> и введи ключ активации.
"""

COMMANDS_TEXT = """
📋 <b>Доступные команды</b>

<b>.spam [текст] [количество]</b>
Спамит указанный текст в чат. Максимум <b>30</b> сообщений.
<i>Пример:</i> <code>.spam Привет! 5</code>

<b>.mute [время]</b>
Мутит пользователя (нужно ответить на его сообщение).
Время: <code>5m</code> (минуты), <code>1h</code> (часы), <code>1d</code> (дни)
<i>Пример:</i> <code>.mute 10m</code>

⚠️ Команды работают только при активном ключе!
"""


@router.message(CommandStart())
async def cmd_start(message: Message):
    admin = await is_admin(message.from_user.id)
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "🤖 Я бот для управления чатами.\n"
        "Используй кнопки ниже для навигации.",
        reply_markup=main_menu(is_admin=admin),
        parse_mode="HTML"
    )
    activated = await is_user_activated(message.from_user.id)
    if not activated and message.from_user.id != CREATOR_ID:
        await message.answer(
            "📌 <b>Первый шаг — получи ключ активации!</b>\n\n"
            "Без ключа бот не будет работать в твоих чатах.\n"
            "Нажми <b>⚙️ Настройка чатов</b> → <b>Ввести ключ ниже</b>.",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "start")
async def cb_start(callback: CallbackQuery):
    admin = await is_admin(callback.from_user.id)
    await callback.message.edit_text(
        f"👋 Привет, <b>{callback.from_user.first_name}</b>!\n\n"
        "🤖 Я бот для управления чатами.\n"
        "Используй кнопки ниже для навигации.",
        reply_markup=main_menu(is_admin=admin),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "tutorial")
async def cb_tutorial(callback: CallbackQuery):
    await callback.message.edit_text(
        TUTORIAL_TEXT,
        reply_markup=back_button("start"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "my_commands")
async def cb_commands(callback: CallbackQuery):
    await callback.message.edit_text(
        COMMANDS_TEXT,
        reply_markup=back_button("start"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "chat_settings")
async def cb_chat_settings(callback: CallbackQuery):
    activated = await is_user_activated(callback.from_user.id)
    activation = await get_activation(callback.from_user.id)
    is_creator = callback.from_user.id == CREATOR_ID

    if is_creator:
        status_line = "✅ Создатель — бот всегда активен"
    elif activated and activation:
        expires = activation.get("expires_at")
        if expires:
            status_line = f"✅ Бот активен до: <code>{expires}</code>"
        else:
            status_line = "✅ Бот активирован навсегда"
    else:
        status_line = "❌ Бот не активирован"

    if activated or is_creator:
        intro = (
            "⚙️ <b>Настройка чатов</b>\n\n"
            f"{status_line}\n\n"
            "Бот подключён и готов к работе в твоих чатах."
        )
    else:
        intro = (
            "⚙️ <b>Настройка чатов</b>\n\n"
            f"{status_line}\n\n"
            "Для работы бота необходим ключ активации.\n"
            "👇 <b>Введите ключ ниже</b> — нажмите кнопку и отправьте ключ."
        )

    await callback.message.edit_text(
        intro,
        reply_markup=chat_settings_menu(activated or is_creator),
        parse_mode="HTML"
    )
