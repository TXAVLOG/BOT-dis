import aiosqlite
import json
import os

DB_PATH = "data/tu_tien.db"

class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def initialize(self):
        os.makedirs("data", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            # Table for users
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT,
                    layer INTEGER DEFAULT 1,
                    exp INTEGER DEFAULT 0,
                    goal INTEGER DEFAULT 200,
                    last_mission_reset REAL DEFAULT 0,
                    missions_completed INTEGER DEFAULT 0,
                    last_daily REAL DEFAULT 0,
                    last_daily_date TEXT,
                    daily_streak INTEGER DEFAULT 0,
                    spirit_stones INTEGER DEFAULT 0,
                    inventory TEXT DEFAULT '[]',
                    missions TEXT DEFAULT '[]',
                    current_mission TEXT DEFAULT NULL,
                    sect_id INTEGER DEFAULT NULL,
                    daily_exp INTEGER DEFAULT 0,
                    last_daily_exp_reset REAL DEFAULT 0,
                    buffs TEXT DEFAULT '{}'
                )
            """)
            
            # Migration check: Add sect_id if not exists
            try:
                await db.execute("ALTER TABLE users ADD COLUMN sect_id INTEGER DEFAULT NULL")
            except: pass
            
            # Migration check: Add daily_exp stats
            try:
                await db.execute("ALTER TABLE users ADD COLUMN daily_exp INTEGER DEFAULT 0")
                await db.execute("ALTER TABLE users ADD COLUMN last_daily_exp_reset REAL DEFAULT 0")
            except: pass

            # Migration check: Add buffs to users
            try:
                await db.execute("ALTER TABLE users ADD COLUMN buffs TEXT DEFAULT '{}'")
            except: pass

            # Table for sects (Updated)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sects (
                    sect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    leader_id TEXT,
                    level INTEGER DEFAULT 1,
                    exp INTEGER DEFAULT 0,
                    description TEXT,
                    kung_fu TEXT DEFAULT '[]'
                )
            """)

            # Migration check: Add kung_fu to sects
            try:
                await db.execute("ALTER TABLE sects ADD COLUMN kung_fu TEXT DEFAULT '[]'")
            except: pass
            
            await db.commit()

    def _parse_user_row(self, row):
        if not row: return None
        data = dict(row)
        data['inventory'] = json.loads(data.get('inventory', '[]'))
        data['missions'] = json.loads(data.get('missions', '[]'))
        data['current_mission'] = json.loads(data['current_mission']) if data.get('current_mission') else None
        data['buffs'] = json.loads(data.get('buffs', '{}'))
        return data

    async def get_user(self, user_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return self._parse_user_row(row)

    async def create_user(self, user_id: str, name: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)",
                (user_id, name)
            )
            await db.commit()

    async def update_user(self, user_id: str, **kwargs):
        if not kwargs:
            return
        
        # Prepare data
        if 'inventory' in kwargs:
            kwargs['inventory'] = json.dumps(kwargs['inventory'], ensure_ascii=False)
        if 'missions' in kwargs:
            kwargs['missions'] = json.dumps(kwargs['missions'], ensure_ascii=False)
        if 'current_mission' in kwargs:
            kwargs['current_mission'] = json.dumps(kwargs['current_mission'], ensure_ascii=False) if kwargs['current_mission'] else None
        if 'buffs' in kwargs:
            kwargs['buffs'] = json.dumps(kwargs['buffs'], ensure_ascii=False)

        keys = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values())
        values.append(user_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE users SET {keys} WHERE user_id = ?", tuple(values))
            await db.commit()

    async def get_top_users(self, limit=10):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users ORDER BY layer DESC, exp DESC LIMIT ?", 
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._parse_user_row(row) for row in rows]

    async def get_all_users(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                return [self._parse_user_row(row) for row in rows]

    async def get_all_sects(self):
        """Lấy danh sách tất cả tông môn"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM sects ORDER BY exp DESC") as cursor:
                rows = await cursor.fetchall()
                res = []
                for r in rows:
                    d = dict(r)
                    d['kung_fu'] = json.loads(d['kung_fu']) if d.get('kung_fu') else []
                    res.append(d)
                return res

    async def update_sect(self, sect_id: int, **kwargs):
        """Cập nhật thông tin tông môn"""
        if not kwargs: return
        
        if 'kung_fu' in kwargs:
            kwargs['kung_fu'] = json.dumps(kwargs['kung_fu'], ensure_ascii=False)
            
        keys = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values())
        values.append(sect_id)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE sects SET {keys} WHERE sect_id = ?", tuple(values))
            await db.commit()

    async def update_sect_exp(self, sect_id: int, exp: int):
        """Cộng thêm EXP cho tông môn"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE sects SET exp = exp + ? WHERE sect_id = ?", (exp, sect_id))
            await db.commit()
