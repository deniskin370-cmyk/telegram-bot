from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


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
    status = "✅ Бот активен" if activated else "❌ Бот не активирован"
    buttons = [
        [InlineKeyboardButton(text=status, callback_data="key_status")],
    ]
    if not activated:
        buttons.append([InlineKeyboardButton(text="🔑 Ввести ключ активации", callback_data="enter_key")])
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


def key_duration_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 день", callback_data="duration_1d"),
            InlineKeyboardButton(text="7 дней", callback_data="duration_7d"),
        ],
        [
            InlineKeyboardButton(text="30 дней", callback_data="duration_30d"),
            InlineKeyboardButton(text="♾ Навсегда", callback_data="duration_forever"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")],
    ])
