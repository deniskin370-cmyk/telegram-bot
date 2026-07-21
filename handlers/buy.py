"""
Покупка ключей за Telegram Stars.
После оплаты бот автоматически отправляет подарок @Neworsi через sendGift.
"""
import logging
import random
import string
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice,
    PreCheckoutQuery
)

from config import NEWORSI_USER_ID
from database import create_key, activate_user

router = Router()
logger = logging.getLogger(__name__)

PLANS = {
    "buy_day":     {"label": "1 день",   "stars": 1,  "days": 1,  "gift_emoji": None},
    "buy_week":    {"label": "1 неделя", "stars": 15, "days": 7,  "gift_emoji": "❤"},
    "buy_month":   {"label": "1 месяц",  "stars": 25, "days": 30, "gift_emoji": "🎁"},
    "buy_forever": {"label": "Навсегда", "stars": 50, "days": None, "gift_emoji": "🎂"},
}


def generate_key(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


async def find_gift_id(bot: Bot, star_count: int, preferred_emoji: str | None = None) -> str | None:
    """Ищет gift_id по количеству звёзд и (опционально) emoji стикера."""
    try:
        result = await bot.get_available_gifts()
        gifts = result.gifts

        # Сначала пробуем найти по звёздам + emoji
        if preferred_emoji:
            for gift in gifts:
                if gift.star_count == star_count and gift.sticker.emoji == preferred_emoji:
                    return gift.id

        # Fallback: просто по количеству звёзд
        for gift in gifts:
            if gift.star_count == star_count:
                return gift.id

    except Exception as e:
        logger.warning("Не удалось получить список подарков: %s", e)

    return None


async def send_gift_to_neworsi(bot: Bot, plan_id: str) -> bool:
    """Отправляет подарок пользователю @Neworsi согласно тарифу."""
    if not NEWORSI_USER_ID:
        logger.error("NEWORSI_USER_ID не задан! Подарок не отправлен.")
        return False

    plan = PLANS.get(plan_id)
    if not plan or not plan["gift_emoji"]:
        return False  # buy_day — без подарка

    gift_id = await find_gift_id(bot, plan["stars"], plan["gift_emoji"])
    if not gift_id:
        logger.warning(
            "Подарок на %d звёзд (emoji=%s) не найден в доступных. Отправляем без фильтра по emoji.",
            plan["stars"], plan["gift_emoji"]
        )
        gift_id = await find_gift_id(bot, plan["stars"])

    if not gift_id:
        logger.error("Не найдено ни одного подарка на %d звёзд.", plan["stars"])
        return False

    try:
        await bot.send_gift(
            user_id=NEWORSI_USER_ID,
            gift_id=gift_id,
        )
        logger.info(
            "Подарок %s (%d звёзд) успешно отправлен @Neworsi (id=%d)",
            plan["gift_emoji"], plan["stars"], NEWORSI_USER_ID
        )
        return True
    except Exception as e:
        logger.error("Ошибка отправки подарка @Neworsi: %s", e)
        return False


# ─── Выбор плана ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"buy_day", "buy_week", "buy_month", "buy_forever"}))
async def cb_buy_plan(callback: CallbackQuery):
    plan_id = callback.data
    plan = PLANS[plan_id]

    await callback.message.answer_invoice(
        title=f"🔑 Ключ — {plan['label']}",
        description=(
            f"Ключ активации бота на {plan['label']}.\n"
            "После оплаты ключ выдаётся автоматически."
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


# ─── Успешная оплата → ключ + автоподарок @Neworsi ────────────────────────────

@router.message(F.successful_payment)
async def payment_done(message: Message):
    payload = message.successful_payment.invoice_payload
    plan = PLANS.get(payload)
    if not plan:
        await message.answer("❌ Ошибка при обработке платежа. Обратитесь в поддержку.")
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

    await activate_user(message.from_user.id, key, expires_at)

    exp_text = f"до <code>{expires_at}</code>" if expires_at else "навсегда"

    await message.answer(
        f"✅ <b>Оплата прошла успешно!</b>\n\n"
        f"🔑 Ключ: <code>{key}</code>\n"
        f"⏳ Срок: <b>{plan['label']}</b> ({exp_text})\n\n"
        "Бот активирован. Не забудь подключить через <b>Автоматизацию чатов</b>.",
        parse_mode="HTML"
    )

    # Автоматически отправляем подарок @Neworsi
    if plan["gift_emoji"]:
        await send_gift_to_neworsi(message.bot, payload)
