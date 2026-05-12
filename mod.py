"""
cogs/moderation/mod.py  –  Moderation commands
kick, ban, unban, softban, mute, unmute, timeout, untimeout
warn, unwarn, clearwarn, warnings, clear
lockchannel, unlockchannel, slowmode
deafen, undeafen, setnick, resetnick
addrole, removerole, delrole
move, voicekick, voiceban
case, cases, reason, duration
modlog, modlogs
"""
import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone

from utils.helpers import (
    success_embed, error_embed, info_embed, warn_embed,
    parse_duration, format_duration, has_mod_role, utcnow, discord_timestamp
)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self._check_expired.start()

    def cog_unload(self):
        self._check_expired.cancel()

    # ── Internal: post to modlog ──────────────────────────────────
    async def _log_action(self, guild: discord.Guild, case_id: int, action: str,
                          user: discord.User, mod: discord.Member, reason: str,
                          duration: str = None):
        cfg = await self.db.get_guild(guild.id)
        ch_id = cfg.get("mod_log_channel_id")
        if not ch_id:
            return
        ch = guild.get_channel(int(ch_id))
        if not ch:
            return
        colors = {
            "ban": 0xE74C3C, "softban": 0xE67E22, "kick": 0xF39C12,
            "mute": 0x9B59B6, "unmute": 0x2ECC71, "warn": 0xF1C40F,
            "unwarn": 0x2ECC71, "timeout": 0x9B59B6, "untimeout": 0x2ECC71,
            "unban": 0x2ECC71, "voiceban": 0xE74C3C, "deafen": 0x95A5A6,
            "undeafen": 0x2ECC71, "clear": 0x3498DB,
        }
        em = discord.Embed(
            color=colors.get(action, 0x95A5A6),
            timestamp=utcnow()
        )
        em.set_author(name=f"{action.upper()} | Case #{case_id}", icon_url=user.display_avatar.url)
        em.add_field(name="User", value=f"{user.mention} (`{user}` | `{user.id}`)")
        em.add_field(name="Moderator", value=f"{mod.mention} (`{mod}`)")
        em.add_field(name="Reason", value=reason, inline=False)
        if duration:
            em.add_field(name="Duration", value=duration)
        em.set_footer(text=f"User ID: {user.id}")
        msg = await ch.send(embed=em)
        await self.db.execute(
            "UPDATE mod_cases SET log_msg_id=? WHERE guild_id=? AND case_id=?",
            (str(msg.id), str(guild.id), case_id)
        )

    # ── Task: un-mute/un-ban expired punishments ──────────────────
    @tasks.loop(seconds=30)
    async def _check_expired(self):
        now = utcnow().isoformat()
        rows = await self.db.fetchall(
            "SELECT * FROM mutes WHERE active=1 AND expires_at IS NOT NULL AND expires_at <= ?",
            (now,)
        )
        for row in rows:
            guild = self.bot.get_guild(int(row["guild_id"]))
            if not guild:
                continue
            member = guild.get_member(int(row["user_id"]))
            cfg = await self.db.get_guild(guild.id)
            mute_role_id = cfg.get("mute_role_id")
            if member and mute_role_id:
                mute_role = guild.get_role(int(mute_role_id))
                if mute_role and mute_role in member.roles:
                    await member.remove_roles(mute_role, reason="Mute expired")
            await self.db.execute(
                "UPDATE mutes SET active=0 WHERE id=?", (row["id"],)
            )

        # temp bans
        brows = await self.db.fetchall(
            "SELECT * FROM bans WHERE active=1 AND expires_at IS NOT NULL AND expires_at <= ?",
            (now,)
        )
        for row in brows:
            guild = self.bot.get_guild(int(row["guild_id"]))
            if not guild:
                continue
            try:
                await guild.unban(discord.Object(id=int(row["user_id"])), reason="Temp ban expired")
            except Exception:
                pass
            await self.db.execute("UPDATE bans SET active=0 WHERE id=?", (row["id"],))

    @_check_expired.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # ─────────────────────────────────────────────────────────────
    # KICK
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Kick a member from the server."""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=error_embed("You can't kick someone with an equal/higher role."))
        try:
            await member.send(embed=info_embed(f"You were kicked from **{ctx.guild.name}**.\nReason: {reason}"))
        except Exception:
            pass
        await member.kick(reason=f"{ctx.author}: {reason}")
        case_id = await self.db.create_case(ctx.guild.id, member.id, str(member), ctx.author.id, str(ctx.author), "kick", reason)
        await ctx.send(embed=success_embed(f"Kicked **{member}** | Case #{case_id}\nReason: {reason}"))
        await self._log_action(ctx.guild, case_id, "kick", member, ctx.author, reason)

    # ─────────────────────────────────────────────────────────────
    # BAN
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.User, duration: str = None, *, reason="No reason provided"):
        """Ban a user. Optional duration: !ban @user 7d Reason."""
        member = ctx.guild.get_member(user.id)
        if member and member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=error_embed("You can't ban someone with an equal/higher role."))

        expires_at = None
        dur_str = None
        if duration:
            td = parse_duration(duration)
            if td:
                expires_at = (utcnow() + td).isoformat()
                dur_str = format_duration(td)
            else:
                reason = f"{duration} {reason}".strip()

        try:
            await user.send(embed=info_embed(f"You were banned from **{ctx.guild.name}**.\nReason: {reason}" + (f"\nDuration: {dur_str}" if dur_str else "")))
        except Exception:
            pass

        await ctx.guild.ban(user, reason=f"{ctx.author}: {reason}", delete_message_days=0)
        await self.db.execute(
            "INSERT OR REPLACE INTO bans(guild_id,user_id,user_tag,mod_id,reason,expires_at) VALUES(?,?,?,?,?,?)",
            (str(ctx.guild.id), str(user.id), str(user), str(ctx.author.id), reason, expires_at)
        )
        case_id = await self.db.create_case(ctx.guild.id, user.id, str(user), ctx.author.id, str(ctx.author), "ban", reason, dur_str, expires_at)
        await ctx.send(embed=success_embed(f"Banned **{user}** | Case #{case_id}\nReason: {reason}" + (f" | Duration: {dur_str}" if dur_str else "")))
        await self._log_action(ctx.guild, case_id, "ban", user, ctx.author, reason, dur_str)

    # ─────────────────────────────────────────────────────────────
    # UNBAN
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int, *, reason="No reason provided"):
        """Unban a user by ID."""
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=f"{ctx.author}: {reason}")
            await self.db.execute("UPDATE bans SET active=0 WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(user_id)))
            case_id = await self.db.create_case(ctx.guild.id, user.id, str(user), ctx.author.id, str(ctx.author), "unban", reason)
            await ctx.send(embed=success_embed(f"Unbanned **{user}** | Case #{case_id}"))
            await self._log_action(ctx.guild, case_id, "unban", user, ctx.author, reason)
        except discord.NotFound:
            await ctx.send(embed=error_embed("That user is not banned or doesn't exist."))

    # ─────────────────────────────────────────────────────────────
    # SOFTBAN
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def softban(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Ban then immediately unban (clears messages)."""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(embed=error_embed("You can't softban someone with an equal/higher role."))
        try:
            await member.send(embed=info_embed(f"You were softbanned from **{ctx.guild.name}**.\nReason: {reason}"))
        except Exception:
            pass
        await ctx.guild.ban(member, reason=f"[SOFTBAN] {ctx.author}: {reason}", delete_message_days=7)
        await ctx.guild.unban(member, reason="Softban - immediately unbanned")
        case_id = await self.db.create_case(ctx.guild.id, member.id, str(member), ctx.author.id, str(ctx.author), "softban", reason)
        await ctx.send(embed=success_embed(f"Softbanned **{member}** | Case #{case_id}\nReason: {reason}"))
        await self._log_action(ctx.guild, case_id, "softban", member, ctx.author, reason)

    # ─────────────────────────────────────────────────────────────
    # MUTE / UNMUTE
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(self, ctx, member: discord.Member, duration: str = None, *, reason="No reason provided"):
        """Mute a member using the mute role."""
        cfg = await self.db.get_guild(ctx.guild.id)
        mute_role_id = cfg.get("mute_role_id")
        if not mute_role_id:
            return await ctx.send(embed=error_embed("No mute role set. Use `setmuterole @role`."))
        mute_role = ctx.guild.get_role(int(mute_role_id))
        if not mute_role:
            return await ctx.send(embed=error_embed("Mute role not found."))
        if mute_role in member.roles:
            return await ctx.send(embed=warn_embed(f"**{member}** is already muted."))

        expires_at = None
        dur_str = None
        if duration:
            td = parse_duration(duration)
            if td:
                expires_at = (utcnow() + td).isoformat()
                dur_str = format_duration(td)
            else:
                reason = f"{duration} {reason}".strip()

        await member.add_roles(mute_role, reason=f"{ctx.author}: {reason}")
        await self.db.execute(
            "INSERT OR REPLACE INTO mutes(guild_id,user_id,mod_id,reason,expires_at) VALUES(?,?,?,?,?)",
            (str(ctx.guild.id), str(member.id), str(ctx.author.id), reason, expires_at)
        )
        case_id = await self.db.create_case(ctx.guild.id, member.id, str(member), ctx.author.id, str(ctx.author), "mute", reason, dur_str, expires_at)
        await ctx.send(embed=success_embed(f"Muted **{member}** | Case #{case_id}" + (f" | Duration: {dur_str}" if dur_str else "")))
        await self._log_action(ctx.guild, case_id, "mute", member, ctx.author, reason, dur_str)

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Unmute a member."""
        cfg = await self.db.get_guild(ctx.guild.id)
        mute_role_id = cfg.get("mute_role_id")
        if not mute_role_id:
            return await ctx.send(embed=error_embed("No mute role set."))
        mute_role = ctx.guild.get_role(int(mute_role_id))
        if not mute_role or mute_role not in member.roles:
            return await ctx.send(embed=warn_embed(f"**{member}** is not muted."))
        await member.remove_roles(mute_role, reason=f"{ctx.author}: {reason}")
        await self.db.execute("UPDATE mutes SET active=0 WHERE guild_id=? AND user_id=?", (str(ctx.guild.id), str(member.id)))
        case_id = await self.db.create_case(ctx.guild.id, member.id, str(member), ctx.author.id, str(ctx.author), "unmute", reason)
        await ctx.send(embed=success_embed(f"Unmuted **{member}** | Case #{case_id}"))
        await self._log_action(ctx.guild, case_id, "unmute", member, ctx.author, reason)

    # ─────────────────────────────────────────────────────────────
    # TIMEOUT / UNTIMEOUT
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, duration: str = "10m", *, reason="No reason provided"):
        """Timeout a member (Discord native). Max 28 days."""
        td = parse_duration(duration)
        if not td:
            return await ctx.send(embed=error_embed("Invalid duration. Example: `10m`, `1h`, `1d`"))
        until = utcnow() + td
        await member.timeout(until, reason=f"{ctx.author}: {reason}")
        case_id = await self.db.create_case(ctx.guild.id, member.id, str(member), ctx.author.id, str(ctx.author), "timeout", reason, format_duration(td), until.isoformat())
        await ctx.send(embed=success_embed(f"Timed out **{member}** for **{format_duration(td)}** | Case #{case_id}"))
        await self._log_action(ctx.guild, case_id, "timeout", member, ctx.author, reason, format_duration(td))

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Remove a timeout from a member."""
        await member.timeout(None, reason=f"{ctx.author}: {reason}")
        case_id = await self.db.create_case(ctx.guild.id, member.id, str(member), ctx.author.id, str(ctx.author), "untimeout", reason)
        await ctx.send(embed=success_embed(f"Removed timeout from **{member}** | Case #{case_id}"))
        await self._log_action(ctx.guild, case_id, "untimeout", member, ctx.author, reason)

    # ─────────────────────────────────────────────────────────────
    # WARN / UNWARN / CLEARWARN / WARNINGS
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @has_mod_role()
    async def warn(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Warn a member."""
        warn_id = await self.db.add_warning(ctx.guild.id, member.id, ctx.author.id, str(ctx.author), reason)
        case_id = await self.db.create_case(ctx.guild.id, member.id, str(member), ctx.author.id, str(ctx.author), "warn", reason)
        total = len(await self.db.get_warnings(ctx.guild.id, member.id))
        try:
            await member.send(embed=warn_embed(f"You received a warning in **{ctx.guild.name}**.\nReason: {reason}"))
        except Exception:
            pass
        await ctx.send(embed=success_embed(f"Warned **{member}** (Warning #{total}) | Case #{case_id}\nReason: {reason}"))
        await self._log_action(ctx.guild, case_id, "warn", member, ctx.author, reason)

    @commands.command()
    @commands.guild_only()
    @has_mod_role()
    async def unwarn(self, ctx, member: discord.Member, warn_id: int):
        """Remove a specific warning by ID."""
        await self.db.remove_warning(ctx.guild.id, warn_id)
        await ctx.send(embed=success_embed(f"Removed warning #{warn_id} from **{member}**."))

    @commands.command()
    @commands.guild_only()
    @has_mod_role()
    async def clearwarn(self, ctx, member: discord.Member):
        """Clear all warnings for a member."""
        await self.db.clear_warnings(ctx.guild.id, member.id)
        await ctx.send(embed=success_embed(f"Cleared all warnings for **{member}**."))

    @commands.command(aliases=["infractions"])
    @commands.guild_only()
    @has_mod_role()
    async def warnings(self, ctx, member: discord.Member):
        """View warnings for a member."""
        warns = await self.db.get_warnings(ctx.guild.id, member.id)
        em = discord.Embed(title=f"Warnings for {member}", color=0xF39C12)
        if not warns:
            em.description = "No active warnings."
        else:
            em.description = "\n".join(
                f"`#{w['id']}` {w['reason']} — by {w['mod_tag']}" for w in warns
            )
            em.set_footer(text=f"Total: {len(warns)} warning(s)")
        await ctx.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # CLEAR (purge messages)
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["purge"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int = 10, member: discord.Member = None):
        """Delete messages. !clear 50 or !clear 20 @user"""
        if amount < 1 or amount > 1000:
            return await ctx.send(embed=error_embed("Amount must be between 1 and 1000."))
        await ctx.message.delete()
        check = (lambda m: m.author == member) if member else None
        deleted = await ctx.channel.purge(limit=amount, check=check)
        msg = await ctx.send(embed=success_embed(f"Deleted **{len(deleted)}** messages" + (f" from **{member}**." if member else ".")))
        await asyncio.sleep(5)
        await msg.delete()

    # ─────────────────────────────────────────────────────────────
    # LOCKCHANNEL / UNLOCKCHANNEL
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockchannel(self, ctx, channel: discord.TextChannel = None, *, reason="Channel locked"):
        """Lock a channel so @everyone can't send messages."""
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, send_messages=False, reason=f"{ctx.author}: {reason}")
        await ctx.send(embed=success_embed(f"🔒 Locked {channel.mention}. Reason: {reason}"))

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlockchannel(self, ctx, channel: discord.TextChannel = None):
        """Unlock a previously locked channel."""
        channel = channel or ctx.channel
        await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(embed=success_embed(f"🔓 Unlocked {channel.mention}."))

    # ─────────────────────────────────────────────────────────────
    # SLOWMODE
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int = 0, channel: discord.TextChannel = None):
        """Set slowmode. !slowmode 10 or !slowmode 0 to disable."""
        channel = channel or ctx.channel
        if seconds < 0 or seconds > 21600:
            return await ctx.send(embed=error_embed("Slowmode must be between 0 and 21600 seconds."))
        await channel.edit(slowmode_delay=seconds)
        if seconds ==
