"""
Поиск по открытым легальным базам данных.
"""
import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

TIMEOUT = aiohttp.ClientTimeout(total=10)


# ─── ФССП — исполнительные производства (долги) ──────────────────────────────

async def search_fssp(first_name: str, last_name: str, patronymic: str = "", region: int = 0) -> str:
    """
    Поиск в базе ФССП (Федеральная служба судебных приставов).
    Показывает активные исполнительные производства.
    """
    url = "https://api-ip.fssprus.ru/api/v1.0/search"
    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "patronymic": patronymic,
        "date": "",
        "region": region,
    }
    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    return f"⚠️ ФССП недоступна (HTTP {resp.status})"
                data = await resp.json(content_type=None)

        result = data.get("result", {})
        items = result.get("items", [])
        if not items:
            return "✅ Исполнительных производств не найдено"

        lines = [f"⚠️ Найдено производств: {len(items)}"]
        for item in items[:3]:  # показываем не больше 3
            name = item.get("name", "—")
            exe_type = item.get("exe_production", "—")
            subject = item.get("subject", "—")
            dep = item.get("department", "—")
            lines.append(f"• <b>{name}</b>\n  📋 {exe_type}\n  💰 {subject}\n  🏢 {dep}")
        if len(items) > 3:
            lines.append(f"  ...и ещё {len(items) - 3}")
        return "\n".join(lines)

    except asyncio.TimeoutError:
        return "⏱ ФССП: превышено время ожидания"
    except Exception as e:
        logger.warning("ФССП ошибка: %s", e)
        return "❌ ФССП: ошибка запроса"


# ─── ФНС ЕГРЮЛ/ЕГРИП — проверка ИП и организаций ────────────────────────────

async def search_nalog(name: str) -> str:
    """
    Поиск в базе ФНС (ЕГРЮЛ / ЕГРИП).
    Показывает зарегистрированные ИП и организации.
    """
    url = "https://egrul.nalog.ru/EGRUL_VSRS/api/search/ul"
    params = {"query": name, "region": "", "page": 1}
    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return f"⚠️ ФНС недоступна (HTTP {resp.status})"
                data = await resp.json(content_type=None)

        items = data.get("rows", [])
        if not items:
            # Пробуем поиск по ИП
            params["page"] = 1
            url_ip = "https://egrul.nalog.ru/EGRUL_VSRS/api/search/ip"
            async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as session:
                async with session.get(url_ip, params=params) as resp:
                    if resp.status == 200:
                        data2 = await resp.json(content_type=None)
                        items = data2.get("rows", [])

        if not items:
            return "✅ Организаций / ИП не найдено"

        lines = [f"🏢 Найдено в ФНС: {len(items)}"]
        for item in items[:3]:
            org_name = item.get("n", item.get("fullName", "—"))
            inn = item.get("i", item.get("inn", "—"))
            status = item.get("o", "—")
            lines.append(f"• <b>{org_name}</b>\n  ИНН: <code>{inn}</code> | {status}")
        if len(items) > 3:
            lines.append(f"  ...и ещё {len(items) - 3}")
        return "\n".join(lines)

    except asyncio.TimeoutError:
        return "⏱ ФНС: превышено время ожидания"
    except Exception as e:
        logger.warning("ФНС ошибка: %s", e)
        return "❌ ФНС: ошибка запроса"


# ─── Общая функция пробива ────────────────────────────────────────────────────

async def lookup_all(full_name: str) -> dict[str, str]:
    """
    Запускает все проверки параллельно.
    Возвращает словарь {источник: результат}.
    """
    parts = full_name.strip().split()
    last = parts[0] if len(parts) >= 1 else full_name
    first = parts[1] if len(parts) >= 2 else ""
    patronymic = parts[2] if len(parts) >= 3 else ""

    fssp_task = search_fssp(first, last, patronymic)
    nalog_task = search_nalog(full_name)

    fssp_result, nalog_result = await asyncio.gather(fssp_task, nalog_task)

    return {
        "fssp": fssp_result,
        "nalog": nalog_result,
    }
