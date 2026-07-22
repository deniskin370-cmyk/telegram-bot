from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from database import is_admin, is_user_activated, get_activation
from keyboards import main_reply_keyboard, back_button, chat_settings_menu, buy_key_menu
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

⚠️ <b>Важно:</b> для работы бота необходим активный ключ.
"""

COMMANDS_TEXT = """
📋 <b>Доступные команды</b>

<b>.spam [текст] [количество]</b>
Спамит текст в чат. Максимум 30 сообщений.
<i>Пример:</i> <code>.spam Привет! 5</code>

<b>.mute [минуты]</b>
Мутит пользователя.
— В группе: ответь на его сообщение
— В ЛС: мутит собеседника, удаляет его сообщения
<i>Пример:</i> <code>.mute 10</code> — замутить на 10 минут

<b>.unmute</b>
Снимает мут с собеседника в ЛС.

⚠️ Команды работают только при активном ключе!
"""

SUPPORT_TEXT = (
    "💬 <b>Поддержка</b>\n\n"
    "Если у вас появилась проблема/жалоба напишите нашему менеджеру:\n\n"
    "👤 @Wincheestersw\n\n"
    "Ответит в течении 24 часов."
)


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    admin = await is_admin(message.from_user.id)
    # Только клавиатура — никаких лишних сообщений
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n"
        "Используй кнопки внизу для навигации.",
        reply_markup=main_reply_keyboard(is_admin=admin),
        parse_mode="HTML"
    )


# ─── Кнопка «⚙️ Настройка чатов» ─────────────────────────────────────────────

async def show_chat_settings(user_id: int, first_name: str, send_fn, state: FSMContext):
    """
    Если не активирован — сразу запрашивает ключ (без промежуточного экрана).
    Если активирован — показывает статус.
    """
    from handlers.keys import KeyState

    is_creator = user_id == CREATOR_ID
    activated = await is_user_activated(user_id)
    activation = await get_activation(user_id)

    if is_creator or activated:
        if is_creator:
            status = "✅ Создатель — бот всегда активен"
        elif activation:
            exp = activation.get("expires_at")
            status = f"✅ Бот активен до: <code>{exp}</code>" if exp else "✅ Бот активирован навсегда"
        else:
            status = "✅ Бот активирован"

        await send_fn(
            f"⚙️ <b>Настройка чатов</b>\n\n{status}\n\nБот готов к работе.",
            reply_markup=chat_settings_menu(True),
            parse_mode="HTML"
        )
    else:
        # Не активирован — сразу просим ключ
        await state.set_state(KeyState.waiting_for_key)
        await send_fn(
            "🔑 <b>Введи ключ активации</b>\n\n"
            "Отправь ключ следующим сообщением.\n"
            "Ключ выдаётся администратором или через раздел <b>🛒 Купить ключ</b>.",
            parse_mode="HTML"
        )


@router.message(F.text == "⚙️ Настройка чатов")
async def reply_chat_settings(message: Message, state: FSMContext):
    await show_chat_settings(
        message.from_user.id,
        message.from_user.first_name,
        message.answer,
        state
    )


@router.callback_query(F.data == "chat_settings")
async def cb_chat_settings(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_chat_settings(
        callback.from_user.id,
        callback.from_user.first_name,
        callback.message.answer,
        state
    )


# ─── Кнопки reply-клавиатуры ──────────────────────────────────────────────────

@router.message(F.text == "📖 Как подключить")
async def reply_tutorial(message: Message):
    await message.answer(TUTORIAL_TEXT, parse_mode="HTML")


@router.message(F.text == "📋 Мои команды")
async def reply_commands(message: Message):
    await message.answer(COMMANDS_TEXT, parse_mode="HTML")


@router.message(F.text == "💬 Поддержка")
async def reply_support(message: Message):
    await message.answer(SUPPORT_TEXT, parse_mode="HTML")


@router.message(F.text == "🛒 Купить ключ")
async def reply_buy_key(message: Message):
    await message.answer(
        "🛒 <b>Купить ключ</b>\n\n"
        "Выбери тариф. После оплаты ключ выдаётся автоматически.\n"
        "Оплата через Telegram Stars ⭐️",
        reply_markup=buy_key_menu(),
        parse_mode="HTML"
    )


@router.message(F.text == "🔑 Панель администратора")
async def reply_admin_panel(message: Message):
    from keyboards import admin_panel_menu
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к панели администратора.")
        return
    await message.answer(
        "🔑 <b>Панель администратора</b>\n\nВыбери действие:",
        reply_markup=admin_panel_menu(is_creator=message.from_user.id == CREATOR_ID),
        parse_mode="HTML"
    )


# ─── Callback «start» (назад) ─────────────────────────────────────────────────

@router.callback_query(F.data == "start")
async def cb_start(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()


# ─── Callback: туториал и команды ─────────────────────────────────────────────

@router.callback_query(F.data == "tutorial")
async def cb_tutorial(callback: CallbackQuery):
    await callback.message.edit_text(TUTORIAL_TEXT, reply_markup=back_button("start"), parse_mode="HTML")


@router.callback_query(F.data == "my_commands")
async def cb_commands(callback: CallbackQuery):
    await callback.message.edit_text(COMMANDS_TEXT, reply_markup=back_button("start"), parse_mode="HTML")
