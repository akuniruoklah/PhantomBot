"""
utils/helpers.py  –  Shared utility functions
"""
import re
import math
import discord
from datetime import datetime, timedelta, timezone


def success_embed(description: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=f"✅ {description}", color=0x2ECC71)
    if title:
        e.title = title
    return e


def error_embed(description: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=f"❌ {description}", color=0xE74C3C)
    if title:
        e.title = title
    return e


def info_embed(description: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=f"ℹ️ {description}", color=0x3498DB)
    if title:
        e.title = title
    return e


def warn_embed(description: str, title: str = None) -> discord.Embed:
    e = discord.Embed(description=f"⚠️ {description}", color=0xF39C12)
    if title:
        e.title = title
    return e


def parse_duration(duration_str: str) -> timedelta | None:
    """Parse strings like '1h30m', '7d', '30s' into timedelta."""
    pattern = re.compile(r"(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
    match = pattern.fullmatch(duration_str.strip().lower())
    if not match or not any(match.groups()):
        return None
    weeks, days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)


def format_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total <= 0:
        return "0s"
    parts = []
    for unit, secs in [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]:
        v, total = divmod(total, secs)
        if v:
            parts.append(f"{v}{unit}")
    return " ".join(parts)


def xp_for_level(level: int) -> int:
    """XP required to reach a given level."""
    return 5 * (level ** 2) + 50 * level + 100


def level_from_xp(xp: int) -> int:
    level = 0
    while xp >= xp_for_level(level):
        xp -= xp_for_level(level)
        level += 1
    return level


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def discord_timestamp(dt: datetime, style: str = "R") -> str:
    """Returns a Discord timestamp string. Styles: t T d D f F R"""
    return f"<t:{int(dt.timestamp())}:{style}>"


def paginate(items: list, per_page: int = 10) -> list[list]:
    return [items[i : i + per_page] for i in range(0, len(items), per_page)]


def has_mod_role():
    """Check decorator: mod role OR manage_guild."""
    async def predicate(ctx):
        if ctx.author.guild_permissions.manage_guild:
            return True
        row = await ctx.bot.db.fetchone(
            "SELECT mod_role_id FROM guilds WHERE guild_id=?", (str(ctx.guild.id),)
        )
        if row and row["mod_role_id"]:
            role = ctx.guild.get_role(int(row["mod_role_id"]))
            if role and role in ctx.author.roles:
                return True
        raise discord.ext.commands.CheckFailure("You need the moderator role.")
    from discord.ext import commands
    return commands.check(predicate)


def has_admin_role():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        row = await ctx.bot.db.fetchone(
            "SELECT admin_role_id FROM guilds WHERE guild_id=?", (str(ctx.guild.id),)
        )
        if row and row["admin_role_id"]:
            role = ctx.guild.get_role(int(row["admin_role_id"]))
            if role and role in ctx.author.roles:
                return True
        raise discord.ext.commands.CheckFailure("You need the admin role.")
    from discord.ext import commands
    return commands.check(predicate)
