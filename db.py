import aiosqlite
from utils import utcnow, iso

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  lang TEXT DEFAULT 'uz',
  premium_until TEXT DEFAULT NULL,
  ocr_credits INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_usage (
  user_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  convert_used INTEGER DEFAULT 0,
  translit_used INTEGER DEFAULT 0,
  PRIMARY KEY (user_id, day)
);

CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  plan_days INTEGER DEFAULT 0,
  ocr_credits INTEGER DEFAULT 0,
  amount INTEGER NOT NULL,
  status TEXT NOT NULL,
  proof_file_id TEXT,
  created_at TEXT NOT NULL,
  approved_by INTEGER,
  approved_at TEXT,
  reject_reason TEXT
);
"""

class DB:
    def __init__(self, path: str):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def ensure_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
            await db.commit()

    async def get_lang(self, user_id: int) -> str:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return row[0] if row else "uz"

    async def set_lang(self, user_id: int, lang: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
            await db.commit()

    async def get_premium_until(self, user_id: int) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT premium_until FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return row[0] if row and row[0] else None

    async def set_premium_until(self, user_id: int, until_iso: str | None):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET premium_until=? WHERE user_id=?", (until_iso, user_id))
            await db.commit()

    async def get_ocr_credits(self, user_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT ocr_credits FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def add_ocr_credits(self, user_id: int, credits: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET ocr_credits=ocr_credits+? WHERE user_id=?", (credits, user_id))
            await db.commit()

    async def consume_ocr_credit(self, user_id: int, credits: int = 1) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT ocr_credits FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            have = int(row[0]) if row else 0
            if have < credits:
                return False
            await db.execute("UPDATE users SET ocr_credits=ocr_credits-? WHERE user_id=?", (credits, user_id))
            await db.commit()
            return True

    async def ensure_usage(self, user_id: int, day: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO daily_usage(user_id, day, convert_used, translit_used) VALUES(?,?,0,0)",
                (user_id, day)
            )
            await db.commit()

    async def get_usage(self, user_id: int, day: str) -> tuple[int, int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT convert_used, translit_used FROM daily_usage WHERE user_id=? AND day=?",
                (user_id, day)
            )
            row = await cur.fetchone()
            if not row:
                return (0, 0)
            return (int(row[0]), int(row[1]))

    async def inc_usage(self, user_id: int, day: str, field: str):
        if field not in ("convert_used", "translit_used"):
            raise ValueError("bad field")
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                f"UPDATE daily_usage SET {field}={field}+1 WHERE user_id=? AND day=?",
                (user_id, day)
            )
            await db.commit()

    async def has_pending(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT 1 FROM payments WHERE user_id=? AND status='pending' LIMIT 1",
                (user_id,)
            )
            return (await cur.fetchone()) is not None

    async def create_payment_premium(self, user_id: int, plan_days: int, amount: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO payments(user_id, kind, plan_days, ocr_credits, amount, status, created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (user_id, "premium", plan_days, 0, amount, "pending", iso(utcnow()))
            )
            await db.commit()
            return int(cur.lastrowid)

    async def create_payment_ocr(self, user_id: int, ocr_credits: int, amount: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO payments(user_id, kind, plan_days, ocr_credits, amount, status, created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (user_id, "ocr", 0, ocr_credits, amount, "pending", iso(utcnow()))
            )
            await db.commit()
            return int(cur.lastrowid)

    async def attach_proof(self, payment_id: int, proof_file_id: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE payments SET proof_file_id=? WHERE id=?", (proof_file_id, payment_id))
            await db.commit()

    async def get_payment(self, payment_id: int):
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id, user_id, kind, plan_days, ocr_credits, amount, status, proof_file_id, created_at "
                "FROM payments WHERE id=?",
                (payment_id,)
            )
            return await cur.fetchone()

    async def mark_approved(self, payment_id: int, admin_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE payments SET status='approved', approved_by=?, approved_at=? WHERE id=?",
                (admin_id, iso(utcnow()), payment_id)
            )
            await db.commit()

    async def mark_rejected(self, payment_id: int, admin_id: int, reason: str | None):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE payments SET status='rejected', approved_by=?, approved_at=?, reject_reason=? WHERE id=?",
                (admin_id, iso(utcnow()), reason, payment_id)
            )
            await db.commit()
