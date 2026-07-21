from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="⚙️ Настройка чатов", callback_data="chat_settings")],
        [InlineKeyboardButton(text="📖 Как подключить бота", callback_data="tutorial")],
        [InlineKeyboardButton(text="📋 Мои команды", callback_data="my_commands")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="🔑 Панель администратора", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_button(callback: str = "start") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=callback)]]
    )


def chat_settings_menu(activated: bool) -> InlineKeyboardMarkup:
    buttons = []
    if activated:
        buttons.append([InlineKeyboardButton(text="✅ Бот активирован", callback_data="key_status")])
    else:
        buttons.append([InlineKeyboardButton(text="🔑 Ввести ключ ниже", callback_data="enter_key")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="start")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_panel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Создать ключ", callback_data="admin_create_key")],
        [InlineKeyboardButton(text="📋 Список ключей", callback_data="admin_list_keys")],
        [InlineKeyboardButton(text="👤 Добавить администратора", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="👥 Список администраторов", callback_data="admin_list_admins")],
        [InlineKeyboardButton(text="🗑 Удалить администратора", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="start")],
    ])


def key_unit_menu() -> InlineKeyboardMarkup:
    """Шаг 1: выбор единицы времени."""
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
    """Шаг 2: выбор количества."""
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
