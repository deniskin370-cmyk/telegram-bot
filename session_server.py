"""
Временный веб-сервер для генерации USERBOT_SESSION через браузер.

Использование:
  1. В Railway временно смени команду запуска на: python session_server.py
  2. Открой публичный URL Railway в браузере
  3. Введи номер телефона и код из Telegram
  4. Скопируй полученную строку в переменную USERBOT_SESSION на Railway
  5. Верни команду запуска обратно: python bot.py
"""
import asyncio
import os
from aiohttp import web
from pyrogram import Client
from pyrogram.errors import (
    PhoneCodeInvalid, PhoneCodeExpired,
    SessionPasswordNeeded, PhoneNumberInvalid,
)
from config import USERBOT_API_ID, USERBOT_API_HASH

PORT = int(os.getenv("PORT", "8080"))

# Временное хранилище: phone_hash и клиент между запросами
_state: dict = {}

HTML_HEAD = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Генерация сессии</title>
<style>
  body { font-family: sans-serif; max-width: 480px; margin: 60px auto; padding: 0 20px;
         background: #1a1a2e; color: #eee; }
  h2 { color: #e94560; }
  input { width: 100%; padding: 12px; margin: 10px 0; border-radius: 8px;
          border: 1px solid #444; background: #16213e; color: #eee; font-size: 16px; }
  button { width: 100%; padding: 14px; background: #e94560; color: white;
           border: none; border-radius: 8px; font-size: 16px; cursor: pointer; }
  .box { background: #16213e; border-radius: 12px; padding: 20px; margin-top: 20px; }
  .session { word-break: break-all; font-family: monospace; font-size: 13px;
             background: #0f3460; padding: 15px; border-radius: 8px; }
  .ok { color: #4ecca3; } .err { color: #e94560; }
  p { line-height: 1.6; }
</style>
</head><body>"""

HTML_TAIL = "</body></html>"


async def page_phone(request: web.Request) -> web.Response:
    error = request.rel_url.query.get("error", "")
    err_html = f'<p class="err">❌ {error}</p>' if error else ""
    html = HTML_HEAD + f"""
    <h2>🔑 Генерация сессии Pyrogram</h2>
    <div class="box">
      <p>Введи номер телефона Telegram (в формате +79991234567).</p>
      {err_html}
      <form method="POST" action="/send_code">
        <input name="phone" type="tel" placeholder="+79991234567" required autofocus>
        <button type="submit">Получить код →</button>
      </form>
    </div>""" + HTML_TAIL
    return web.Response(text=html, content_type="text/html")


async def handle_send_code(request: web.Request) -> web.Response:
    data = await request.post()
    phone = str(data.get("phone", "")).strip()
    if not phone:
        raise web.HTTPFound("/?error=Введи+номер+телефона")

    try:
        client = Client(
            name="session_web",
            api_id=USERBOT_API_ID,
            api_hash=USERBOT_API_HASH,
            in_memory=True,
        )
        await client.connect()
        sent = await client.send_code(phone)
        _state["client"] = client
        _state["phone"] = phone
        _state["phone_code_hash"] = sent.phone_code_hash
    except PhoneNumberInvalid:
        raise web.HTTPFound(f"/?error=Неверный+номер+телефона")
    except Exception as e:
        raise web.HTTPFound(f"/?error={str(e)[:80]}")

    html = HTML_HEAD + """
    <h2>📲 Введи код</h2>
    <div class="box">
      <p>Telegram прислал тебе код в приложение.<br>
         Введи его ниже (цифры без пробелов).</p>
      <form method="POST" action="/verify_code">
        <input name="code" type="text" inputmode="numeric"
               placeholder="12345" required autofocus maxlength="10">
        <button type="submit">Подтвердить →</button>
      </form>
    </div>""" + HTML_TAIL
    return web.Response(text=html, content_type="text/html")


async def handle_verify_code(request: web.Request) -> web.Response:
    data = await request.post()
    code = str(data.get("code", "")).strip().replace(" ", "")

    client: Client = _state.get("client")
    phone: str = _state.get("phone", "")
    phone_code_hash: str = _state.get("phone_code_hash", "")

    if not client or not phone or not phone_code_hash:
        raise web.HTTPFound("/?error=Сессия+истекла,+начни+заново")

    try:
        await client.sign_in(
            phone_number=phone,
            phone_code_hash=phone_code_hash,
            phone_code=code,
        )
    except (PhoneCodeInvalid, PhoneCodeExpired):
        raise web.HTTPFound("/?error=Неверный+или+просроченный+код")
    except SessionPasswordNeeded:
        # 2FA включена — запросим пароль
        raise web.HTTPFound("/two_factor")
    except Exception as e:
        raise web.HTTPFound(f"/?error={str(e)[:80]}")

    session_string = await client.export_session_string()
    await client.disconnect()
    _state.clear()

    html = HTML_HEAD + f"""
    <h2 class="ok">✅ Сессия создана!</h2>
    <div class="box">
      <p><b>1.</b> Скопируй строку ниже:</p>
      <div class="session">{session_string}</div>
      <br>
      <p><b>2.</b> На Railway → Variables добавь:<br>
         <code>USERBOT_SESSION</code> = (вставь строку выше)</p>
      <p><b>3.</b> Верни команду запуска на <code>python bot.py</code> и задеплой.</p>
    </div>""" + HTML_TAIL
    return web.Response(text=html, content_type="text/html")


async def handle_two_factor(request: web.Request) -> web.Response:
    error = request.rel_url.query.get("error", "")
    err_html = f'<p class="err">❌ {error}</p>' if error else ""
    html = HTML_HEAD + f"""
    <h2>🔐 Двухфакторная аутентификация</h2>
    <div class="box">
      <p>На аккаунте включён пароль 2FA. Введи его.</p>
      {err_html}
      <form method="POST" action="/verify_2fa">
        <input name="password" type="password" placeholder="Пароль 2FA" required autofocus>
        <button type="submit">Войти →</button>
      </form>
    </div>""" + HTML_TAIL
    return web.Response(text=html, content_type="text/html")


async def handle_verify_2fa(request: web.Request) -> web.Response:
    data = await request.post()
    password = str(data.get("password", ""))
    client: Client = _state.get("client")
    if not client:
        raise web.HTTPFound("/?error=Сессия+истекла,+начни+заново")
    try:
        await client.check_password(password)
    except Exception as e:
        raise web.HTTPFound(f"/two_factor?error={str(e)[:60]}")

    session_string = await client.export_session_string()
    await client.disconnect()
    _state.clear()

    html = HTML_HEAD + f"""
    <h2 class="ok">✅ Сессия создана!</h2>
    <div class="box">
      <p><b>1.</b> Скопируй строку ниже:</p>
      <div class="session">{session_string}</div>
      <br>
      <p><b>2.</b> На Railway → Variables добавь:<br>
         <code>USERBOT_SESSION</code> = (вставь строку выше)</p>
      <p><b>3.</b> Верни команду запуска на <code>python bot.py</code> и задеплой.</p>
    </div>""" + HTML_TAIL
    return web.Response(text=html, content_type="text/html")


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", page_phone)
    app.router.add_post("/send_code", handle_send_code)
    app.router.add_post("/verify_code", handle_verify_code)
    app.router.add_get("/two_factor", handle_two_factor)
    app.router.add_post("/verify_2fa", handle_verify_2fa)
    return app


if __name__ == "__main__":
    print(f"Запуск на порту {PORT}")
    web.run_app(make_app(), port=PORT)
