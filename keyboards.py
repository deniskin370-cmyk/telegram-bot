from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)


# ─── Reply-клавиатура (внизу чата, где пишешь) ───────────────────────────────

def main_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Постоянная клавиатура внизу чата."""
    buttons = [
        [KeyboardButton(text="⚙️ Настройка чатов"), KeyboardButton(text="🛒 Купить ключ")],
        [KeyboardButton(text="📋 Мои команды"), KeyboardButton(text="💬 Поддержка")],
        [KeyboardButton(text="📖 Как подключить")],
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="🔑 Панель администратора")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        persistent=True
    )


# ─── Inline-клавиатуры ────────────────────────────────────────────────────────

def back_button(callback: str = "start") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=callback)]]
    )


def chat_settings_menu(activated: bool) -> InlineKeyboardMarkup:
    buttons = []
    if activated:
        buttons.append([InlineKeyboardButton(text="✅ Бот активирован", callback_data="key_status")])
    else:
        buttons.append([InlineKeyboardButton(text="🔑 Ввести ключ", callback_data="enter_key")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_panel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔑 Создать ключ", callback_data="admin_create_key")],
        [InlineKeyboardButton(text="📋 Список ключей", callback_data="admin_list_keys")],
        [InlineKeyboardButton(text="🚫 Обнулить ключ", callback_data="admin_deactivate_key")],
        [InlineKeyboardButton(text="👤 Добавить администратора", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="👥 Список администраторов", callback_data="admin_list_admins")],
        [InlineKeyboardButton(text="🗑 Удалить администратора", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="start")],
    ])


def key_unit_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏰ Часы", callback_data="kunit_hours"),
            InlineKeyboardButton(text="📅 Дни", callback_data="kunit_days"),
        ],
        [
            InlineKeyboardButton(text="📆 Месяцы", callback_data="kunit_months"),
            InlineKeyboardButton(text="♾ Навсегда", callback_data="kunit_forever"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")],
    ])


def key_amount_menu(unit: str) -> InlineKeyboardMarkup:
    if unit == "hours":
        amounts = [1, 2, 3, 4, 5, 6, 12, 24]
        label = "ч"
    elif unit == "days":
        amounts = [1, 2, 3, 4, 5, 7, 14, 30]
        label = "д"
    else:  # months
        amounts = [1, 2, 3, 6, 12]
        label = "мес"

    buttons = []
    row = []
    for i, a in enumerate(amounts):
        row.append(InlineKeyboardButton(
            text=f"{a}{label}",
            callback_data=f"kamount_{unit}_{a}"
        ))
        if len(row) == 4 or i == len(amounts) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_create_key")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def buy_key_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 1 день — 1 ⭐️",    callback_data="buy_day")],
        [InlineKeyboardButton(text="📅 1 неделя — 15 ⭐️", callback_data="buy_week")],
        [InlineKeyboardButton(text="📆 1 месяц — 25 ⭐️",  callback_data="buy_month")],
        [InlineKeyboardButton(text="♾ Навсегда — 50 ⭐️",  callback_data="buy_forever")],
    ])
