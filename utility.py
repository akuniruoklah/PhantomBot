"""
cogs/utility/utility.py  –  Utility commands
avatar, userinfo, serverinfo, roleinfo, channelinfo
ping, stats, invite, support, about, prefix
say, announce, announcehere
calc, flip, roll, choose, 8ball, joke, cat, dog, pug
translate, urban, define, weather, time, date
afk, afkset, afkremove
count, playtime, rank, ranks
"""
import asyncio
import random
import math
import os
import aiohttp
import discord
from discord.ext import commands
from datetime import datetime, timezone

from utils.helpers import (
    success_embed, error_embed, info_embed, warn_embed,
    utcnow, discord_timestamp, level_from_xp, xp_for_level
)

EIGHT_BALL = [
    "It is certain.", "It is decidedly so.", "Without a doubt.",
    "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
    "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful."
]

JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "I told my wife she was drawing her eyebrows too high. She looked surprised.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I'm reading a book about anti-gravity. It's impossible to put down.",
    "Did you hear about the mathematician who's afraid of negative numbers? He'll stop at nothing to avoid them.",
    "Why don't eggs tell jokes? They'd crack each other up.",
    "What do you call fake spaghetti? An impasta.",
    "I would tell you a construction joke, but I'm still working on it.",
]


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self._session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self._session:
            await self._session.close()

    # ─────────────────────────────────────────────────────────────
    # PING
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    async def ping(self, ctx):
        """Check bot latency."""
        ws = round(self.bot.latency * 1000)
        start = discord.utils.utcnow()
        msg = await ctx.send("🏓 Pinging...")
        end = discord.utils.utcnow()
        api = round((end - start).total_seconds() * 1000)
        em = discord.Embed(title="🏓 Pong!", color=0x2ECC71)
        em.add_field(name="WebSocket", value=f"`{ws}ms`")
        em.add_field(name="API", value=f"`{api}ms`")
        await msg.edit(content=None, embed=em)

    # ─────────────────────────────────────────────────────────────
    # STATS / ABOUT
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    async def stats(self, ctx):
        """Bot statistics."""
        row = await self.db.fetchone("SELECT * FROM bot_stats WHERE id=1")
        uptime_start = datetime.fromisoformat(row["started_at"]).replace(tzinfo=timezone.utc)
        uptime_delta = utcnow() - uptime_start
        h, rem = divmod(int(uptime_delta.total_seconds()), 3600)
        m, s = divmod(rem, 60)
        em = discord.Embed(title=f"{self.bot.user.name} Stats", color=0x3498DB)
        em.set_thumbnail(url=self.bot.user.display_avatar.url)
        em.add_field(name="Servers", value=str(len(self.bot.guilds)))
        em.add_field(name="Users", value=str(len(self.bot.users)))
        em.add_field(name="Uptime", value=f"{h}h {m}m {s}s")
        em.add_field(name="Commands Run", value=str(row["commands_run"]))
        em.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms")
        import sys
        em.add_field(name="Python", value=sys.version.split()[0])
        em.add_field(name="discord.py", value=discord.__version__)
        em.set_footer(text=f"Bot ID: {self.bot.user.id}")
        await ctx.send(embed=em)

    @commands.command()
    async def about(self, ctx):
        await ctx.invoke(self.stats)

    # ─────────────────────────────────────────────────────────────
    # PREFIX
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx, new_prefix: str = None):
        """View or change the bot prefix."""
        if not new_prefix:
            current = await self.db.get_prefix(ctx.guild.id)
            return await ctx.send(embed=info_embed(f"Current prefix: `{current}`"))
        if len(new_prefix) > 5:
            return await ctx.send(embed=error_embed("Prefix must be 5 characters or fewer."))
        await self.db.set_prefix(ctx.guild.id, new_prefix)
        await ctx.send(embed=success_embed(f"Prefix changed to `{new_prefix}`."))

    # ─────────────────────────────────────────────────────────────
    # INVITE / SUPPORT
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    async def invite(self, ctx):
        """Get the bot invite link."""
        url = os.getenv("BOT_INVITE", f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot%20applications.commands")
        em = discord.Embed(description=f"[Click here to invite me!]({url})", color=0x7289DA)
        await ctx.send(embed=em)

    @commands.command()
    async def support(self, ctx):
        """Support server link."""
        url = os.getenv("SUPPORT_SERVER", "https://discord.gg/support")
        await ctx.send(embed=info_embed(f"[Join the support server]({url})"))

    # ─────────────────────────────────────────────────────────────
    # AVATAR
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["av", "pfp"])
    async def avatar(self, ctx, member: discord.Member = None):
        """Get a member's avatar."""
        member = member or ctx.author
        em = discord.Embed(color=member.color)
        em.set_author(name=f"{member.display_name}'s Avatar")
        em.set_image(url=member.display_avatar.url)
        em.description = f"[PNG]({member.display_avatar.with_format('png').url}) | [JPG]({member.display_avatar.with_format('jpg').url}) | [WEBP]({member.display_avatar.with_format('webp').url})"
        await ctx.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # USERINFO
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["ui", "whois"])
    @commands.guild_only()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Get info about a member."""
        member = member or ctx.author
        roles = [r.mention for r in reversed(member.roles) if r.id != ctx.guild.id]
        em = discord.Embed(color=member.color, timestamp=utcnow())
        em.set_author(name=str(member), icon_url=member.display_avatar.url)
        em.set_thumbnail(url=member.display_avatar.url)
        em.add_field(name="ID", value=member.id)
        em.add_field(name="Nickname", value=member.nick or "None")
        em.add_field(name="Account Created", value=discord_timestamp(member.created_at, "D"), inline=False)
        em.add_field(name="Joined Server", value=discord_timestamp(member.joined_at, "D"), inline=False)
        em.add_field(name="Roles", value=", ".join(roles[:15]) or "None", inline=False)
        flags = [f.name.replace("_", " ").title() for f, v in member.public_flags if v]
        if flags:
            em.add_field(name="Badges", value=", ".join(flags))
        em.set_footer(text=f"Requested by {ctx.author}")
        await ctx.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # SERVERINFO
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["si", "guildinfo"])
    @commands.guild_only()
    async def serverinfo(self, ctx):
        """Get server information."""
        g = ctx.guild
        em = discord.Embed(title=g.name, color=0x3498DB, timestamp=utcnow())
        em.set_thumbnail(url=g.icon.url if g.icon else None)
        em.add_field(name="Owner", value=g.owner.mention if g.owner else "Unknown")
        em.add_field(name="ID", value=g.id)
        em.add_field(name="Members", value=f"👥 {g.member_count}")
        em.add_field(name="Channels", value=f"💬 {len(g.text_channels)} | 🔊 {len(g.voice_channels)}")
        em.add_field(name="Roles", value=str(len(g.roles)))
        em.add_field(name="Emojis", value=str(len(g.emojis)))
        em.add_field(name="Boosts", value=f"{g.premium_subscription_count} (Level {g.premium_tier})")
        em.add_field(name="Verification", value=str(g.verification_level).title())
        em.add_field(name="Created", value=discord_timestamp(g.created_at, "D"), inline=False)
        await ctx.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # ROLEINFO
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["ri"])
    @commands.guild_only()
    async def roleinfo(self, ctx, role: discord.Role):
        """Get info about a role."""
        em = discord.Embed(title=f"Role: {role.name}", color=role.color, timestamp=utcnow())
        em.add_field(name="ID", value=role.id)
        em.add_field(name="Color", value=str(role.color))
        em.add_field(name="Members", value=str(len(role.members)))
        em.add_field(name="Hoisted", value="Yes" if role.hoist else "No")
        em.add_field(name="Mentionable", value="Yes" if role.mentionable else "No")
        em.add_field(name="Position", value=str(role.position))
        em.add_field(name="Created", value=discord_timestamp(role.created_at, "D"), inline=False)
        await ctx.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # CHANNELINFO
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["ci"])
    @commands.guild_only()
    async def channelinfo(self, ctx, channel: discord.TextChannel = None):
        """Get info about a channel."""
        ch = channel or ctx.channel
        em = discord.Embed(title=f"#{ch.name}", color=0x3498DB)
        em.add_field(name="ID", value=ch.id)
        em.add_field(name="Category", value=ch.category.name if ch.category else "None")
        em.add_field(name="Topic", value=ch.topic or "None", inline=False)
        em.add_field(name="NSFW", value="Yes" if ch.is_nsfw() else "No")
        em.add_field(name="Slowmode", value=f"{ch.slowmode_delay}s")
        em.add_field(name="Created", value=discord_timestamp(ch.created_at, "D"), inline=False)
        await ctx.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # SAY / ANNOUNCE / ANNOUNCEHERE
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx, *, message: str):
        """Make the bot say something."""
        await ctx.message.delete()
        await ctx.send(message)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(mention_everyone=True)
    async def announce(self, ctx, channel: discord.TextChannel, *, message: str):
        """Send an announcement to a channel."""
        em = discord.Embed(description=message, color=0xE74C3C, timestamp=utcnow())
        em.set_footer(text=f"Announcement by {ctx.author}")
        await channel.send(embed=em)
        await ctx.send(embed=success_embed(f"Announcement sent to {channel.mention}."))

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(mention_everyone=True)
    async def announcehere(self, ctx, *, message: str):
        """Announce in the current channel."""
        await ctx.invoke(self.announce, channel=ctx.channel, message=message)

    # ─────────────────────────────────────────────────────────────
    # FUN COMMANDS
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    async def calc(self, ctx, *, expression: str):
        """Calculate a math expression."""
        try:
            import mathparse
            result = mathparse.parse(expression)
            await ctx.send(embed=info_embed(f"`{expression}` = **{result}**"))
        except Exception:
            try:
                safe = expression.replace("^", "**")
                result = eval(safe, {"__builtins__": {}}, {k: getattr(math, k) for k in dir(math)})
                await ctx.send(embed=info_embed(f"`{expression}` = **{result}**"))
            except Exception:
                await ctx.send(embed=error_embed("Invalid expression."))

    @commands.command()
    async def flip(self, ctx):
        """Flip a coin."""
        result = random.choice(["Heads 🪙", "Tails 🪙"])
        await ctx.send(embed=info_embed(f"**{result}**!"))

    @commands.command()
    async def roll(self, ctx, dice: str = "1d6"):
        """Roll dice. Format: NdN (e.g. 2d20)"""
        try:
            n, sides = map(int, dice.lower().split("d"))
            if n < 1 or n > 100 or sides < 2 or sides > 10000:
                raise ValueError
            rolls = [random.randint(1, sides) for _ in range(n)]
            total = sum(rolls)
            desc = f"**Rolls:** {', '.join(map(str, rolls))}\n**Total:** {total}"
            await ctx.send(embed=info_embed(desc, title=f"🎲 {dice}"))
        except Exception:
            await ctx.send(embed=error_embed("Format: `1d6`, `2d20`, etc."))

    @commands.command()
    async def choose(self, ctx, *choices: str):
        """Choose between options. Separate with spaces (use quotes for phrases)."""
        if len(choices) < 2:
            return await ctx.send(embed=error_embed("Provide at least 2 choices."))
        picked = random.choice(choices)
        await ctx.send(embed=info_embed(f"I choose: **{picked}**"))

    @commands.command(name="8ball", aliases=["8b"])
    async def eightball(self, ctx, *, question: str):
        """Ask the magic 8-ball."""
        answer = random.choice(EIGHT_BALL)
        em = discord.Embed(color=0x2C3E50)
        em.add_field(name="❓ Question", value=question)
        em.add_field(name="🎱 Answer", value=answer, inline=False)
        await ctx.send(embed=em)

    @commands.command()
    async def joke(self, ctx):
        """Get a random joke."""
        await ctx.send(embed=info_embed(random.choice(JOKES)))

    @commands.command()
    async def cat(self, ctx):
        """Random cat image 🐱"""
        try:
            async with self._session.get("https://api.thecatapi.com/v1/images/search") as r:
                data = await r.json()
            url = data[0]["url"]
            em = discord.Embed(color=0xFFA500)
            em.set_image(url=url)
            em.set_footer(text="🐱 Meow!")
            await ctx.send(embed=em)
        except Exception:
            await ctx.send(embed=error_embed("Couldn't fetch a cat image."))

    @commands.command()
    async def dog(self, ctx):
        """Random dog image 🐶"""
        try:
            async with self._session.get("https://dog.ceo/api/breeds/image/random") as r:
                data = await r.json()
            em = discord.Embed(color=0x8B4513)
            em.set_image(url=data["message"])
            em.set_footer(text="🐶 Woof!")
            await ctx.send(embed=em)
        except Exception:
            await ctx.send(embed=error_embed("Couldn't fetch a dog image."))

    @commands.command()
    async def pug(self, ctx):
        """Random pug image 🐾"""
        try:
            async with self._session.get("https://dog.ceo/api/breed/pug/images/random") as r:
                data = await r.json()
            em = discord.Embed(color=0xD2691E)
            em.set_image(url=data["message"])
            em.set_footer(text="🐾 Pug!")
            await ctx.send(embed=em)
        except Exception:
            await ctx.send(embed=error_embed("Couldn't fetch a pug image."))

    # ─────────────────────────────────────────────────────────────
    # TRANSLATE
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    async def translate(self, ctx, lang: str, *, text: str):
        """Translate text. !translate es Hello World"""
        try:
            from translate import Translator
            translator = Translator(to_lang=lang)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: translator.translate(text))
            em = discord.Embed(color=0x3498DB)
            em.add_field(name="Original", value=text[:1024])
            em.add_field(name=f"Translated ({lang.upper()})", value=result[:1024], inline=False)
            await ctx.send(embed=em)
        except Exception as e:
            await ctx.send(embed=error_embed(f"Translation failed: {e}"))

    # ─────────────────────────────────────────────────────────────
    # URBAN / DEFINE
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    async def urban(self, ctx, *, term: str):
        """Look up a term on Urban Dictionary."""
        try:
            async with self._session.get(f"https://api.urbandictionary.com/v0/define?term={term}") as r:
                data = await r.json()
            if not data.get("list"):
                return await ctx.send(embed=error_embed(f"No definition found for **{term}**."))
            result = data["list"][0]
            em = discord.Embed(
                title=result["word"],
                url=result["permalink"],
                description=result["definition"][:2000],
                color=0x1D2439
            )
            em.add_field(name="Example", value=result.get("example", "N/A")[:1024] or "N/A")
            em.set_footer(text=f"👍 {result['thumbs_up']} 👎 {result['thumbs_down']}")
            await ctx.send(embed=em)
        except Exception:
            await ctx.send(embed=error_embed("Urban Dictionary request failed."))

    @commands.command()
    async def define(self, ctx, *, word: str):
        """Define a word using Free Dictionary API."""
        try:
            async with self._session.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}") as r:
                if r.status != 200:
                    return await ctx.send(embed=error_embed(f"No definition found for **{word}**."))
                data = await r.json()
            entry = data[0]
            meanings = entry.get("meanings", [])
            em = discord.Embed(title=entry["word"], color=0x3498DB)
            for m in meanings[:2]:
                defs = m.get("definitions", [])
                if defs:
                    em.add_field(
                        name=m["partOfSpeech"].capitalize(),
                        value=defs[0]["definition"][:1024],
                        inline=False
                    )
            await ctx.send(embed=em)
        except Exception:
            await ctx.send(embed=error_embed("Dictionary API request failed."))

    # ─────────────────────────────────────────────────────────────
    # WEATHER
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    async def weather(self, ctx, *, city: str):
        """Get weather for a city."""
        api_key = os.getenv("WEATHER_API_KEY")
        if not api_key:
            return await ctx.send(embed=error_embed("Weather API key not configured."))
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
            async with self._session.get(url) as r:
                if r.status != 200:
                    return await ctx.send(embed=error_embed(f"City **{city}** not found."))
                data = await r.json()
            desc = data["weather"][
