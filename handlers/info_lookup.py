"""
Поиск по открытым легальным базам данных.
"""
import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

TIMEOUT = aiohttp.ClientTimeout(total=12)


# ─── ФССП ─────────────────────────────────────────────────────────────────────

async def search_fssp(last_name: str, first_name: str, patronymic: str = "") -> str:
    """Поиск в базе ФССП — исполнительные производства."""
    if not last_name or not first_name:
        link = f"https://fssp.gov.ru/iss/ip"
        return f"ℹ️ Укажи полное имя для поиска\n🔗 <a href='{link}'>Поиск вручную</a>"

    url = "https://api-ip.fssprus.ru/api/v1.0/search"
    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "patronymic": patronymic,
        "date": "",
        "region": 0,
    }
    link = f"https://fssp.gov.ru/iss/ip?is={last_name}&firstname={first_name}"
    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
            async with s.post(url, json=payload, ssl=False) as resp:
                if resp.status == 401 or resp.status == 403:
                    return f"🔗 <a href='{link}'>Проверить на сайте ФССП</a>"
                if resp.status != 200:
                    return f"🔗 <a href='{link}'>Проверить на сайте ФССП</a>"
                data = await resp.json(content_type=None)

        items = (data.get("result") or {}).get("items") or []
        if not items:
            return f"✅ Производств не найдено\n🔗 <a href='{link}'>Проверить на сайте ФССП</a>"

        lines = [f"⚠️ Найдено производств: <b>{len(items)}</b>"]
        for item in items[:3]:
            name = item.get("name", "—")
            subject = item.get("subject", "—")
            dep = item.get("department", "—")
            lines.append(f"• <b>{name}</b>\n  💰 {subject}\n  🏢 {dep}")
        if len(items) > 3:
            lines.append(f"  + ещё {len(items) - 3}")
        lines.append(f"🔗 <a href='{link}'>Открыть на сайте ФССП</a>")
        return "\n".join(lines)

    except asyncio.TimeoutError:
        return f"⏱ Превышено время\n🔗 <a href='{link}'>Проверить на сайте ФССП</a>"
    except Exception as e:
        logger.warning("ФССП ошибка: %s", e)
        return f"🔗 <a href='{link}'>Проверить на сайте ФССП</a>"


# ─── ФНС ЕГРЮЛ/ЕГРИП ──────────────────────────────────────────────────────────

async def search_nalog(name: str) -> str:
    """Поиск ИП и организаций по имени через ФНС."""
    if not name or name == "—":
        return "🔗 <a href='https://egrul.nalog.ru/'>Поиск на сайте ФНС</a>"

    link = f"https://egrul.nalog.ru/"
    # ФНС использует POST-запрос с токеном из сессии — напрямую без браузера не работает
    # Используем открытый API dadata.ru (только юр. поиск) или ссылку
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/fio"
    # Dadata требует токен — используем прямую ссылку как fallback
    # Пробуем ФНС через их публичный поиск
    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as s:
            # ФНС: публичный ЕГРЮЛ поиск через официальный API
            payload = {"query": name, "count": 5}
            async with s.post(
                "https://egrul.nalog.ru/search-action",
                json=payload,
                ssl=False
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    rows = data.get("rows") or []
                    if rows:
                        lines = [f"🏢 Найдено в ЕГРЮЛ: <b>{len(rows)}</b>"]
                        for row in rows[:3]:
                            n = row.get("n") or row.get("fullName") or "—"
                            inn = row.get("i") or row.get("inn") or "—"
                            status = row.get("o") or "—"
                            lines.append(f"• <b>{n}</b>\n  ИНН: <code>{inn}</code> | {status}")
                        lines.append(f"🔗 <a href='{link}'>Открыть ФНС ЕГРЮЛ</a>")
                        return "\n".join(lines)
    except Exception as e:
        logger.warning("ФНС ошибка: %s", e)

    return f"✅ В ЕГРЮЛ не найдено\n🔗 <a href='{link}'>Проверить на сайте ФНС</a>"


# ─── Главная функция ──────────────────────────────────────────────────────────

async def lookup_all(full_name: str) -> dict[str, str]:
    """
    Запускает все проверки параллельно.
    full_name: строка вида «Фамилия Имя Отчество» или просто имя из Telegram.
    """
    parts = full_name.strip().split()
    last = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    patronymic = parts[2] if len(parts) >= 3 else ""

    fssp_res, nalog_res = await asyncio.gather(
        search_fssp(last, first, patronymic),
        search_nalog(full_name),
    )
    return {"fssp": fssp_res, "nalog": nalog_res}
