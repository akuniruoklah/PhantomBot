"""
database/db.py  –  Async SQLite manager using aiosqlite
"""
import aiosqlite
import asyncio
import json
import os
import logging
from pathlib import Path

log = logging.getLogger("bot.db")

DB_PATH = os.getenv("DB_PATH", "data/database.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    def __init__(self):
        self._db: aiosqlite.Connection | None = None

    async def connect(self):
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(DB_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._db.execute("PRAGMA cache_size=-64000")
        await self._db.execute("PRAGMA temp_store=MEMORY")
        await self._apply_schema()
        log.info("Database connected: %s", DB_PATH)

    async def _apply_schema(self):
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        await self._db.executescript(schema)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    # ─── Helpers ────────────────────────────────────────────────
    async def execute(self, query: str, params=()) -> aiosqlite.Cursor:
        cur = await self._db.execute(query, params)
        await self._db.commit()
        return cur

    async def fetchone(self, query: str, params=()) -> aiosqlite.Row | None:
        cur = await self._db.execute(query, params)
        return await cur.fetchone()

    async def fetchall(self, query: str, params=()) -> list[aiosqlite.Row]:
        cur = await self._db.execute(query, params)
        return await cur.fetchall()

    async def executemany(self, query: str, params_list):
        await self._db.executemany(query, params_list)
        await self._db.commit()

    # ─── Guild helpers ───────────────────────────────────────────
    async def get_guild(self, guild_id: int) -> dict:
        row = await self.fetchone(
            "SELECT * FROM guilds WHERE guild_id = ?", (str(guild_id),)
        )
        if row is None:
            await self.execute(
                "INSERT OR IGNORE INTO guilds(guild_id) VALUES(?)", (str(guild_id),)
            )
            row = await self.fetchone(
                "SELECT * FROM guilds WHERE guild_id = ?", (str(guild_id),)
            )
        return dict(row)

    async def get_prefix(self, guild_id: int) -> str:
        row = await self.fetchone(
            "SELECT prefix FROM guilds WHERE guild_id = ?", (str(guild_id),)
        )
        return row["prefix"] if row else "!"

    async def set_prefix(self, guild_id: int, prefix: str):
        await self.execute(
            "INSERT INTO guilds(guild_id, prefix) VALUES(?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET prefix=excluded.prefix",
            (str(guild_id), prefix),
        )

    # ─── Mod case helpers ────────────────────────────────────────
    async def next_case_id(self, guild_id: int) -> int:
        row = await self.fetchone(
            "SELECT MAX(case_id) as m FROM mod_cases WHERE guild_id=?",
            (str(guild_id),),
        )
        return (row["m"] or 0) + 1

    async def create_case(
        self,
        guild_id: int,
        user_id: int,
        user_tag: str,
        mod_id: int,
        mod_tag: str,
        action: str,
        reason: str = "No reason provided",
        duration: str = None,
        expires_at: str = None,
    ) -> int:
        case_id = await self.next_case_id(guild_id)
        await self.execute(
            """INSERT INTO mod_cases
               (case_id,guild_id,user_id,user_tag,mod_id,mod_tag,action,reason,duration,expires_at)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                case_id,
                str(guild_id),
                str(user_id),
                user_tag,
                str(mod_id),
                mod_tag,
                action,
                reason,
                duration,
                expires_at,
            ),
        )
        return case_id

    async def get_case(self, guild_id: int, case_id: int) -> dict | None:
        row = await self.fetchone(
            "SELECT * FROM mod_cases WHERE guild_id=? AND case_id=?",
            (str(guild_id), case_id),
        )
        return dict(row) if row else None

    async def get_user_cases(self, guild_id: int, user_id: int) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM mod_cases WHERE guild_id=? AND user_id=? ORDER BY case_id DESC",
            (str(guild_id), str(user_id)),
        )
        return [dict(r) for r in rows]

    async def update_case_reason(self, guild_id: int, case_id: int, reason: str):
        await self.execute(
            "UPDATE mod_cases SET reason=? WHERE guild_id=? AND case_id=?",
            (reason, str(guild_id), case_id),
        )

    # ─── Warning helpers ─────────────────────────────────────────
    async def add_warning(
        self, guild_id: int, user_id: int, mod_id: int, mod_tag: str, reason: str
    ) -> int:
        cur = await self.execute(
            "INSERT INTO warnings(guild_id,user_id,mod_id,mod_tag,reason) VALUES(?,?,?,?,?)",
            (str(guild_id), str(user_id), str(mod_id), mod_tag, reason),
        )
        return cur.lastrowid

    async def get_warnings(self, guild_id: int, user_id: int) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM warnings WHERE guild_id=? AND user_id=? AND active=1 ORDER BY id",
            (str(guild_id), str(user_id)),
        )
        return [dict(r) for r in rows]

    async def remove_warning(self, guild_id: int, warn_id: int):
        await self.execute(
            "UPDATE warnings SET active=0 WHERE id=? AND guild_id=?",
            (warn_id, str(guild_id)),
        )

    async def clear_warnings(self, guild_id: int, user_id: int):
        await self.execute(
            "UPDATE warnings SET active=0 WHERE guild_id=? AND user_id=?",
            (str(guild_id), str(user_id)),
        )

    # ─── Level helpers ───────────────────────────────────────────
    async def get_level(self, guild_id: int, user_id: int) -> dict:
        row = await self.fetchone(
            "SELECT * FROM levels WHERE guild_id=? AND user_id=?",
            (str(guild_id), str(user_id)),
        )
        if row is None:
            await self.execute(
                "INSERT OR IGNORE INTO levels(guild_id,user_id) VALUES(?,?)",
                (str(guild_id), str(user_id)),
            )
            row = await self.fetchone(
                "SELECT * FROM levels WHERE guild_id=? AND user_id=?",
                (str(guild_id), str(user_id)),
            )
        return dict(row)

    async def add_xp(self, guild_id: int, user_id: int, xp: int):
        await self.execute(
            """INSERT INTO levels(guild_id,user_id,xp,total_messages,last_xp_at)
               VALUES(?,?,?,1,datetime('now'))
               ON CONFLICT(guild_id,user_id) DO UPDATE SET
                 xp = xp + excluded.xp,
                 total_messages = total_messages + 1,
                 last_xp_at = excluded.last_xp_at""",
            (str(guild_id), str(user_id), xp),
        )

    async def set_level(self, guild_id: int, user_id: int, level: int):
        await self.execute(
            "UPDATE levels SET level=? WHERE guild_id=? AND user_id=?",
            (level, str(guild_id), str(user_id)),
        )

    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT ?",
            (str(guild_id), limit),
        )
        return [dict(r) for r in rows]

    # ─── Giveaway helpers ────────────────────────────────────────
    async def create_giveaway(self, **kwargs) -> int:
        cur = await self.execute(
            """INSERT INTO giveaways
               (guild_id,channel_id,message_id,host_id,prize,winners_count,ends_at,required_role,min_level)
               VALUES(:guild_id,:channel_id,:message_id,:host_id,:prize,:winners_count,:ends_at,:required_role,:min_level)""",
            kwargs,
        )
        return cur.lastrowid

    async def get_active_giveaways(self, guild_id: int) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM giveaways WHERE guild_id=? AND status='active'",
            (str(guild_id),),
        )
        return [dict(r) for r in rows]

    async def end_giveaway(self, message_id: str, winners: list, ended_at: str):
        await self.execute(
            "UPDATE giveaways SET status='ended',winners=?,ended_at=? WHERE message_id=?",
            (json.dumps(winners), ended_at, message_id),
        )

    # ─── Reminder helpers ────────────────────────────────────────
    async def add_reminder(
        self, user_id: int, channel_id: int, reminder: str, remind_at: str, guild_id: int = None
    ) -> int:
        cur = await self.execute(
            "INSERT INTO reminders(user_id,guild_id,channel_id,reminder,remind_at) VALUES(?,?,?,?,?)",
            (str(user_id), str(guild_id) if guild_id else None, str(channel_id), reminder, remind_at),
        )
        return cur.lastrowid

    async def get_due_reminders(self) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM reminders WHERE remind_at <= datetime('now') AND sent=0"
        )
        return [dict(r) for r in rows]

    async def mark_reminder_sent(self, reminder_id: int):
        await self.execute(
            "UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,)
        )

    async def get_user_reminders(self, user_id: int) -> list[dict]:
        rows = await self.fetchall(
            "SELECT * FROM reminders WHERE user_id=? AND sent=0 ORDER BY remind_at",
            (str(user_id),),
        )
        return [dict(r) for r in rows]

    # ─── AFK helpers ─────────────────────────────────────────────
    async def set_afk(self, guild_id: int, user_id: int, reason: str = "AFK"):
        await self.execute(
            "INSERT OR REPLACE INTO afk(guild_id,user_id,reason,since) VALUES(?,?,?,datetime('now'))",
            (str(guild_id), str(user_id), reason),
        )

    async def remove_afk(self, guild_id: int, user_id: int):
        await self.execute(
            "DELETE FROM afk WHERE guild_id=? AND user_id=?",
            (str(guild_id), str(user_id)),
        )

    async def get_afk(self, guild_id: int, user_id: int) -> dict | None:
        row = await self.fetchone(
            "SELECT * FROM afk WHERE guild_id=? AND user_id=?",
            (str(guild_id), str(user_id)),
        )
        return dict(row) if row else None

    # ─── Stat tracking ───────────────────────────────────────────
    async def log_command(self, command_name: str, guild_id, user_id: int):
        await self.execute(
            "INSERT INTO command_stats(command_name,guild_id,user_id) VALUES(?,?,?)",
            (command_name, str(guild_id) if guild_id else None, str(user_id)),
        )
        await self.execute(
            "UPDATE bot_stats SET commands_run=commands_run+1 WHERE id=1"
        )


# Singleton
db = Database()
