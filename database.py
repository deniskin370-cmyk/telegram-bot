"""
Database layer — поддерживает PostgreSQL (Railway, DATABASE_URL) и SQLite (локально).
1 ключ = 1 пользователь: после активации ключ привязывается к user_id.
"""
import os
import asyncpg
import aiosqlite
from datetime import datetime
from config import DB_PATH, CREATOR_ID

DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = bool(DATABASE_URL)

_pg_pool = None


async def get_pool():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pg_pool


# ─── Init ─────────────────────────────────────────────────────────────────────

async def init_db():
    if USE_POSTGRES:
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
            # Миграция: добавить used_by если уже существует таблица без него
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
            if CREATOR_ID:
                await conn.execute("""
                    INSERT INTO admins (user_id, username)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id) DO NOTHING
                """, CREATOR_ID, "Creator")
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    added_at TEXT DEFAULT (datetime('now'))
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    created_by INTEGER,
                    expires_at TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    is_active INTEGER DEFAULT 1,
                    used_by INTEGER DEFAULT NULL
                )
            """)
            # Миграция: добавить used_by если уже существует таблица без него
            try:
                await db.execute("ALTER TABLE keys ADD COLUMN used_by INTEGER DEFAULT NULL")
            except Exception:
                pass
            await db.execute("""
                CREATE TABLE IF NOT EXISTS activations (
                    user_id INTEGER PRIMARY KEY,
                    key_used TEXT,
                    activated_at TEXT DEFAULT (datetime('now')),
                    expires_at TEXT
                )
            """)
            if CREATOR_ID:
                await db.execute(
                    "INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)",
                    (CREATOR_ID, "Creator")
                )
            await db.commit()


# ─── Admins ───────────────────────────────────────────────────────────────────

async def is_admin(user_id: int) -> bool:
    if user_id == CREATOR_ID:
        return True
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT 1 FROM admins WHERE user_id = $1", user_id)
            return row is not None
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cur:
                return await cur.fetchone() is not None


async def add_admin(user_id: int, username: str = "") -> bool:
    try:
        if USE_POSTGRES:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO admins (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    user_id, username
                )
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                await db.commit()
        return True
    except Exception:
        return False


async def remove_admin(user_id: int) -> bool:
    try:
        if USE_POSTGRES:
            pool = await get_pool()
            async with pool.acquire() as conn:
                result = await conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)
                return result != "DELETE 0"
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
                await db.commit()
                return cur.rowcount > 0
    except Exception:
        return False


async def get_all_admins() -> list[dict]:
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, username, added_at FROM admins")
            return [dict(r) for r in rows]
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT user_id, username, added_at FROM admins") as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]


# ─── Keys ─────────────────────────────────────────────────────────────────────

async def create_key(key: str, created_by: int, expires_at: str | None) -> bool:
    try:
        if USE_POSTGRES:
            pool = await get_pool()
            async with pool.acquire() as conn:
                expires = None
                if expires_at:
                    expires = datetime.fromisoformat(expires_at)
                await conn.execute(
                    "INSERT INTO keys (key, created_by, expires_at) VALUES ($1, $2, $3)",
                    key, created_by, expires
                )
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO keys (key, created_by, expires_at) VALUES (?, ?, ?)",
                    (key, created_by, expires_at)
                )
                await db.commit()
        return True
    except Exception:
        return False


async def get_key(key: str) -> dict | None:
    """
    Возвращает ключ только если он активен И ещё не использован (used_by IS NULL).
    """
    if USE_POSTGRES:
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
                # Проверка срока действия самого ключа
                if datetime.now() > d["expires_at"].replace(tzinfo=None):
                    return None
                d["expires_at"] = str(d["expires_at"])
            return d
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM keys WHERE key = ? AND is_active = 1 AND used_by IS NULL",
                (key,)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return None
                d = dict(row)
                if d.get("expires_at"):
                    try:
                        if datetime.now() > datetime.fromisoformat(d["expires_at"]):
                            return None
                    except Exception:
                        pass
                return d


async def get_all_keys() -> list[dict]:
    if USE_POSTGRES:
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
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, key, created_by, expires_at, created_at, is_active, used_by "
                "FROM keys ORDER BY created_at DESC LIMIT 50"
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]


# ─── Activations ──────────────────────────────────────────────────────────────

async def activate_user(user_id: int, key: str, expires_at: str | None) -> bool:
    """
    Активирует пользователя и привязывает ключ к нему (1 ключ = 1 пользователь).
    """
    try:
        if USE_POSTGRES:
            pool = await get_pool()
            async with pool.acquire() as conn:
                expires = None
                if expires_at:
                    try:
                        expires = datetime.fromisoformat(expires_at)
                    except Exception:
                        expires = None
                async with conn.transaction():
                    # Привязываем ключ к пользователю
                    await conn.execute(
                        "UPDATE keys SET used_by = $1 WHERE key = $2 AND used_by IS NULL",
                        user_id, key
                    )
                    # Сохраняем активацию
                    await conn.execute("""
                        INSERT INTO activations (user_id, key_used, expires_at)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (user_id) DO UPDATE
                        SET key_used = $2, activated_at = NOW(), expires_at = $3
                    """, user_id, key, expires)
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                # Привязываем ключ к пользователю
                await db.execute(
                    "UPDATE keys SET used_by = ? WHERE key = ? AND used_by IS NULL",
                    (user_id, key)
                )
                # Сохраняем активацию
                await db.execute("""
                    INSERT OR REPLACE INTO activations (user_id, key_used, expires_at)
                    VALUES (?, ?, ?)
                """, (user_id, key, expires_at))
                await db.commit()
        return True
    except Exception:
        return False


async def is_user_activated(user_id: int) -> bool:
    if user_id == CREATOR_ID:
        return True
    if USE_POSTGRES:
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
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT expires_at FROM activations WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return False
                expires_at = row[0]
                if expires_at is None:
                    return True
                try:
                    return datetime.now() < datetime.fromisoformat(expires_at)
                except Exception:
                    return True


async def get_activation(user_id: int) -> dict | None:
    if USE_POSTGRES:
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
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM activations WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None
