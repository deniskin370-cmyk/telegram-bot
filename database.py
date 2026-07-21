"""
Database layer — только PostgreSQL (Neon / Railway).
Для подключения установи переменную окружения DATABASE_URL.
Данные (ключи, админы, пользователи) НЕ сбрасываются при перезапуске бота.
"""
import os
import asyncpg
from datetime import datetime
from config import CREATOR_ID

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError(
        "❌ DATABASE_URL не задан!\n"
        "Создай БД на https://neon.tech и добавь DATABASE_URL в переменные окружения."
    )

_pg_pool = None


async def get_pool():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pg_pool


# ─── Init ─────────────────────────────────────────────────────────────────────

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                added_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                created_by BIGINT,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                is_active BOOLEAN DEFAULT TRUE,
                used_by BIGINT DEFAULT NULL
            )
        """)
        await conn.execute("""
            ALTER TABLE keys ADD COLUMN IF NOT EXISTS used_by BIGINT DEFAULT NULL
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS activations (
                user_id BIGINT PRIMARY KEY,
                key_used TEXT,
                activated_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS muted_users (
                user_id BIGINT PRIMARY KEY,
                muted_until TIMESTAMP NOT NULL
            )
        """)
        if CREATOR_ID:
            await conn.execute("""
                INSERT INTO admins (user_id, username)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO NOTHING
            """, CREATOR_ID, "Creator")


# ─── Admins ───────────────────────────────────────────────────────────────────

async def is_admin(user_id: int) -> bool:
    if user_id == CREATOR_ID:
        return True
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM admins WHERE user_id = $1", user_id)
        return row is not None


async def add_admin(user_id: int, username: str = "") -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO admins (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                user_id, username
            )
        return True
    except Exception:
        return False


async def remove_admin(user_id: int) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)
            return result != "DELETE 0"
    except Exception:
        return False


async def get_all_admins() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, username, added_at FROM admins")
        return [dict(r) for r in rows]


# ─── Keys ─────────────────────────────────────────────────────────────────────

async def create_key(key: str, created_by: int, expires_at: str | None) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            expires = None
            if expires_at:
                expires = datetime.fromisoformat(expires_at)
            await conn.execute(
                "INSERT INTO keys (key, created_by, expires_at) VALUES ($1, $2, $3)",
                key, created_by, expires
            )
        return True
    except Exception:
        return False


async def get_key(key: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM keys WHERE key = $1 AND is_active = TRUE AND used_by IS NULL",
            key
        )
        if not row:
            return None
        d = dict(row)
        if d.get("expires_at"):
            if datetime.now() > d["expires_at"].replace(tzinfo=None):
                return None
            d["expires_at"] = str(d["expires_at"])
        return d


async def get_all_keys() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, key, created_by, expires_at, created_at, is_active, used_by "
            "FROM keys ORDER BY created_at DESC LIMIT 50"
        )
        result = []
        for r in rows:
            d = dict(r)
            if d.get("expires_at"):
                d["expires_at"] = str(d["expires_at"])
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            result.append(d)
        return result


# ─── Activations ──────────────────────────────────────────────────────────────

async def activate_user(user_id: int, key: str, expires_at: str | None) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            expires = None
            if expires_at:
                try:
                    expires = datetime.fromisoformat(expires_at)
                except Exception:
                    expires = None
            async with conn.transaction():
                await conn.execute(
                    "UPDATE keys SET used_by = $1 WHERE key = $2 AND used_by IS NULL",
                    user_id, key
                )
                await conn.execute("""
                    INSERT INTO activations (user_id, key_used, expires_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id) DO UPDATE
                    SET key_used = $2, activated_at = NOW(), expires_at = $3
                """, user_id, key, expires)
        return True
    except Exception:
        return False


async def is_user_activated(user_id: int) -> bool:
    if user_id == CREATOR_ID:
        return True
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT expires_at FROM activations WHERE user_id = $1", user_id
        )
        if not row:
            return False
        expires_at = row["expires_at"]
        if expires_at is None:
            return True
        return datetime.now() < expires_at.replace(tzinfo=None)


async def get_activation(user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM activations WHERE user_id = $1", user_id
        )
        if not row:
            return None
        d = dict(row)
        if d.get("expires_at"):
            d["expires_at"] = str(d["expires_at"])
        if d.get("activated_at"):
            d["activated_at"] = str(d["activated_at"])
        return d


# ─── Mute (для ЛС через business mode) ───────────────────────────────────────

async def mute_user(user_id: int, muted_until: datetime) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO muted_users (user_id, muted_until)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET muted_until = $2
            """, user_id, muted_until)
        return True
    except Exception:
        return False


async def is_muted(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT muted_until FROM muted_users WHERE user_id = $1", user_id
        )
        if not row:
            return False
        muted_until = row["muted_until"]
        if datetime.now() < muted_until.replace(tzinfo=None):
            return True
        await conn.execute("DELETE FROM muted_users WHERE user_id = $1", user_id)
        return False


async def unmute_user(user_id: int) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM muted_users WHERE user_id = $1", user_id)
        return True
    except Exception:
        return False
