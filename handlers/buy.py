"""
Покупка ключей за Telegram Stars.
Stars поступают на аккаунт @Neworsi (настраивается в @BotFather → Monetization).
"""
import random
import string
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice,
    PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

from database import create_key, activate_user

router = Router()

PLANS = {
    "buy_day":     {"label": "1 день",   "stars": 1,  "days": 1},
    "buy_week":    {"label": "1 неделя", "stars": 15, "days": 7},
    "buy_month":   {"label": "1 месяц",  "stars": 25, "days": 30},
    "buy_forever": {"label": "Навсегда", "stars": 50, "days": None},
}

# Подарок, который нужно отправить @Neworsi перед оплатой
GIFT_INFO = {
    "buy_week": {
        "emoji": "❤️",
        "name": "Сердечко",
        "text": (
            "📩 <b>Перед оплатой отправьте подарок!</b>\n\n"
            "Пожалуйста, отправьте подарок ❤️ <b>Сердечко</b> пользователю @Neworsi:\n\n"
            "1️⃣ Нажмите кнопку ниже, чтобы открыть профиль @Neworsi\n"
            "2️⃣ Нажмите на иконку 🎁 → выберите подарок ❤️ Сердечко\n"
            "3️⃣ После отправки подарка вернитесь и нажмите оплатить ниже"
        ),
    },
    "buy_month": {
        "emoji": "🎁",
        "name": "Подарок",
        "text": (
            "📩 <b>Перед оплатой отправьте подарок!</b>\n\n"
            "Пожалуйста, отправьте подарок 🎁 пользователю @Neworsi:\n\n"
            "1️⃣ Нажмите кнопку ниже, чтобы открыть профиль @Neworsi\n"
            "2️⃣ Нажмите на иконку 🎁 → выберите нужный подарок\n"
            "3️⃣ После отправки подарка вернитесь и нажмите оплатить ниже"
        ),
    },
    "buy_forever": {
        "emoji": "🎂",
        "name": "Торт",
        "text": (
            "📩 <b>Перед оплатой отправьте подарок!</b>\n\n"
            "Пожалуйста, отправьте подарок 🎂 <b>Торт</b> пользователю @Neworsi:\n\n"
            "1️⃣ Нажмите кнопку ниже, чтобы открыть профиль @Neworsi\n"
            "2️⃣ Нажмите на иконку 🎁 → выберите подарок 🎂 Торт\n"
            "3️⃣ После отправки подарка вернитесь и нажмите оплатить ниже"
        ),
    },
}


def generate_key(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def gift_keyboard(plan_id: str) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой открыть @Neworsi и кнопкой оплатить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Открыть профиль @Neworsi", url="https://t.me/Neworsi")],
        [InlineKeyboardButton(text="✅ Я отправил подарок — оплатить", callback_data=f"pay_now_{plan_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy_back")],
    ])


# ─── Выбор плана ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"buy_day", "buy_week", "buy_month", "buy_forever"}))
async def cb_buy_plan(callback: CallbackQuery):
    plan_id = callback.data
    plan = PLANS[plan_id]
    gift = GIFT_INFO.get(plan_id)

    if gift:
        # Тарифы с подарком: сначала показываем сообщение с просьбой отправить подарок
        await callback.message.edit_text(
            gift["text"],
            reply_markup=gift_keyboard(plan_id),
            parse_mode="HTML"
        )
    else:
        # buy_day — сразу выставляем инвойс
        await callback.message.answer_invoice(
            title=f"🔑 Ключ — {plan['label']}",
            description=(
                f"Ключ активации бота на {plan['label']}.\n"
                "После оплаты ключ будет выдан автоматически."
            ),
            payload=plan_id,
            currency="XTR",
            prices=[LabeledPrice(label=f"Ключ {plan['label']}", amount=plan["stars"])],
        )

    await callback.answer()


@router.callback_query(F.data == "buy_back")
async def cb_buy_back(callback: CallbackQuery):
    from keyboards import buy_key_menu
    await callback.message.edit_text(
        "🛒 <b>Купить ключ</b>\n\n"
        "Выбери тариф. После оплаты ключ выдаётся автоматически.\n"
        "Оплата через Telegram Stars ⭐️",
        reply_markup=buy_key_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_now_"))
async def cb_pay_now(callback: CallbackQuery):
    """Пользователь отправил подарок и нажал «Оплатить»."""
    plan_id = callback.data.replace("pay_now_", "")
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("❌ Неизвестный тариф.", show_alert=True)
        return

    await callback.message.answer_invoice(
        title=f"🔑 Ключ — {plan['label']}",
        description=(
            f"Ключ активации бота на {plan['label']}.\n"
            "После оплаты ключ будет выдан автоматически."
        ),
        payload=plan_id,
        currency="XTR",
        prices=[LabeledPrice(label=f"Ключ {plan['label']}", amount=plan["stars"])],
    )
    await callback.answer()


# ─── Подтверждение оплаты ─────────────────────────────────────────────────────

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


# ─── Успешная оплата → создать и выдать ключ ──────────────────────────────────

@router.message(F.successful_payment)
async def payment_done(message: Message):
    payload = message.successful_payment.invoice_payload
    plan = PLANS.get(payload)
    if not plan:
        await message.answer("❌ Произошла ошибка при обработке платежа. Обратитесь в поддержку.")
        return

    # Создаём ключ
    key = generate_key()
    if plan["days"] is not None:
        expires_at = (datetime.now() + timedelta(days=plan["days"])).strftime("%Y-%m-%d %H:%M:%S")
    else:
        expires_at = None

    key_ok = await create_key(key, 0, expires_at)
    if not key_ok:
        await message.answer("❌ Ошибка создания ключа. Обратитесь в поддержку: @Wincheestersw")
        return

    # Сразу активируем пользователя
    await activate_user(message.from_user.id, key, expires_at)

    if expires_at:
        exp_text = f"до <code>{expires_at}</code>"
    else:
        exp_text = "навсегда"

    gift = GIFT_INFO.get(payload)
    gift_line = f"\n\n🎁 Не забудьте отправить подарок {gift['emoji']} @Neworsi, если ещё не сделали!" if gift else ""

    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"🔑 Ключ: <code>{key}</code>\n"
        f"⏳ Срок: <b>{plan['label']}</b> ({exp_text})\n\n"
        f"Бот активирован. Команды уже работают в твоих чатах!\n"
        f"Не забудь подключить бота через <b>Автоматизацию чатов</b>.{gift_line}",
        parse_mode="HTML"
    )
