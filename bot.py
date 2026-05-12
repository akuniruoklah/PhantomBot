"""
bot.py  –  Main bot class
"""
import os
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database.db import db

load_dotenv()
log = logging.getLogger("bot")


async def get_prefix(bot: "Bot", message: discord.Message):
    if not message.guild:
        return commands.when_mentioned_or("!")(bot, message)
    prefix = await db.get_prefix(message.guild.id)
    return commands.when_mentioned_or(prefix)(bot, message)


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.db = db

    async def setup_hook(self):
        await db.connect()
        await self._load_cogs()
        await self.tree.sync()
        log.info("Bot setup complete.")

    async def _load_cogs(self):
        cogs_dir = Path(__file__).parent / "cogs"
        for folder in cogs_dir.iterdir():
            if folder.is_dir():
                for file in folder.glob("*.py"):
                    ext = f"cogs.{folder.name}.{file.stem}"
                    try:
                        await self.load_extension(ext)
                        log.info("Loaded: %s", ext)
                    except Exception as e:
                        log.error("Failed %s: %s", ext, e)

    async def on_ready(self):
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | !help",
            )
        )
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        log.info("Guilds: %d | Users: %d", len(self.guilds), len(self.users))

    async def on_guild_join(self, guild: discord.Guild):
        await db.get_guild(guild.id)   # auto-insert defaults
        log.info("Joined guild: %s (%d)", guild.name, guild.id)

    async def on_command(self, ctx: commands.Context):
        await db.log_command(ctx.command.qualified_name, ctx.guild.id if ctx.guild else None, ctx.author.id)

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CommandNotFound):
            # check custom commands
            cmd = ctx.invoked_with.lower()
            row = await db.fetchone(
                "SELECT response,embed FROM custom_commands WHERE guild_id=? AND name=?",
                (str(ctx.guild.id) if ctx.guild else "0", cmd),
            )
            if row:
                await db.execute(
                    "UPDATE custom_commands SET uses=uses+1 WHERE guild_id=? AND name=?",
                    (str(ctx.guild.id), cmd),
                )
                if row["embed"]:
                    em = discord.Embed(description=row["response"], color=discord.Color.blurple())
                    return await ctx.send(embed=em)
                return await ctx.send(row["response"])
            return

        if isinstance(error, commands.MissingPermissions):
            return await ctx.send(f"❌ You're missing: `{'`, `'.join(error.missing_permissions)}`")
        if isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(f"❌ I'm missing: `{'`, `'.join(error.missing_permissions)}`")
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send(f"❌ Missing argument: `{error.param.name}`")
        if isinstance(error, commands.BadArgument):
            return await ctx.send(f"❌ Bad argument: {error}")
        if isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(f"⏳ Cooldown! Try again in `{error.retry_after:.1f}s`")
        if isinstance(error, commands.NoPrivateMessage):
            return await ctx.send("❌ This command can't be used in DMs.")
        if isinstance(error, commands.CheckFailure):
            return await ctx.send("❌ You don't have permission to use this command.")

        log.error("Unhandled error in %s: %s", ctx.command, error, exc_info=error)
        await ctx.send(f"❌ An unexpected error occurred: `{error}`")

    async def close(self):
        await db.close()
        await super().close()
