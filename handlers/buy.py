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
    PreCheckoutQuery
)

from database import create_key, activate_user

router = Router()

PLANS = {
    "buy_week":    {"label": "1 неделя",  "stars": 15, "days": 7},
    "buy_month":   {"label": "1 месяц",   "stars": 25, "days": 30},
    "buy_forever": {"label": "Навсегда",  "stars": 50, "days": None},
}


def generate_key(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


# ─── Выбор плана ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"buy_week", "buy_month", "buy_forever"}))
async def cb_buy_plan(callback: CallbackQuery):
    plan_id = callback.data
    plan = PLANS[plan_id]

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

    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"🔑 Ключ: <code>{key}</code>\n"
        f"⏳ Срок: <b>{plan['label']}</b> ({exp_text})\n\n"
        "Бот активирован. Команды уже работают в твоих чатах!\n"
        "Не забудь подключить бота через <b>Автоматизацию чатов</b>."
    )
