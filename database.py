import aiosqlite
from datetime import datetime
from config import DB_PATH, CREATOR_ID


async def init_db():
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
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS activations (
                user_id INTEGER PRIMARY KEY,
                key_used TEXT,
                activated_at TEXT DEFAULT (datetime('now')),
                expires_at TEXT
            )
        """)
        # Добавляем создателя как администратора при инициализации
        if CREATOR_ID:
            await db.execute("""
                INSERT OR IGNORE INTO admins (user_id, username)
                VALUES (?, ?)
            """, (CREATOR_ID, "Creator"))
        await db.commit()


# ─── Admins ───────────────────────────────────────────────────────────────────

async def is_admin(user_id: int) -> bool:
    if user_id == CREATOR_ID:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone() is not None


async def add_admin(user_id: int, username: str = "") -> bool:
    try:
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
    if user_id == CREATOR_ID:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()
    return True


async def get_all_admins() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM admins ORDER BY added_at DESC") as cur:
            return list(await cur.fetchall())


# ─── Keys ─────────────────────────────────────────────────────────────────────

async def create_key(key: str, created_by: int, expires_at: str | None = None) -> bool:
    try:
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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM keys WHERE key = ? AND is_active = 1", (key,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def deactivate_key(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE keys SET is_active = 0 WHERE key = ?", (key,))
        await db.commit()


async def get_all_keys() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM keys ORDER BY created_at DESC LIMIT 20") as cur:
            return list(await cur.fetchall())


# ─── Activations ──────────────────────────────────────────────────────────────

async def activate_user(user_id: int, key: str, expires_at: str | None = None) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO activations (user_id, key_used, activated_at, expires_at)
                VALUES (?, ?, datetime('now'), ?)
            """, (user_id, key, expires_at))
            await db.commit()
        return True
    except Exception:
        return False


async def is_user_activated(user_id: int) -> bool:
    if user_id == CREATOR_ID:
        return True
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
                exp = datetime.fromisoformat(expires_at)
                return datetime.now() < exp
            except Exception:
                return True


async def get_activation(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM activations WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
