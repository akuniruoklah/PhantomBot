"""
cogs/music/music.py  –  Music commands using discord.py + yt-dlp
play, pause, resume, stop, skip, skipto, queue, np
volume, leave, remove, clearqueue, loop, shuffle, lyrics, search
"""
import asyncio
import random
import discord
from discord.ext import commands
from collections import deque
import yt_dlp
import os

from utils.helpers import error_embed, success_embed, info_embed, warn_embed

YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "noplaylist": True,
    "extract_flat": False,
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class Song:
    def __init__(self, data: dict, requester: discord.Member):
        self.url = data.get("url") or data.get("webpage_url")
        self.stream_url = data.get("url")
        self.title = data.get("title", "Unknown")
        self.duration = data.get("duration", 0)
        self.thumbnail = data.get("thumbnail")
        self.webpage_url = data.get("webpage_url", self.url)
        self.requester = requester
        self.uploader = data.get("uploader", "Unknown")

    @property
    def duration_str(self):
        if not self.duration:
            return "Live"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def embed(self) -> discord.Embed:
        em = discord.Embed(title=self.title, url=self.webpage_url, color=0x1DB954)
        em.set_thumbnail(url=self.thumbnail)
        em.add_field(name="Duration", value=self.duration_str)
        em.add_field(name="Uploader", value=self.uploader)
        em.add_field(name="Requested by", value=self.requester.mention)
        return em


class GuildPlayer:
    def __init__(self):
        self.queue: deque[Song] = deque()
        self.current: Song | None = None
        self.volume: float = 1.0
        self.loop: str = "off"          # off | song | queue
        self.shuffle_on: bool = False
        self.voice_client: discord.VoiceClient | None = None
        self.text_channel: discord.TextChannel | None = None
        self._lock = asyncio.Lock()


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}

    def get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer()
        return self.players[guild_id]

    async def _fetch_song(self, query: str, requester: discord.Member) -> Song | None:
        if not query.startswith("http"):
            query = f"ytsearch:{query}"
        loop = asyncio.get_event_loop()
        try:
            with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
            if "entries" in data:
                data = data["entries"][0]
            return Song(data, requester)
        except Exception as e:
            return None

    def _play_next(self, guild_id: int, error=None):
        player = self.get_player(guild_id)
        if error:
            self.bot.loop.call_soon_threadsafe(
                asyncio.ensure_future,
                player.text_channel.send(embed=error_embed(f"Playback error: {error}"))
            )

        if player.loop == "song" and player.current:
            player.queue.appendleft(player.current)
        elif player.loop == "queue" and player.current:
            player.queue.append(player.current)

        if player.queue:
            if player.shuffle_on:
                idx = random.randint(0, len(player.queue) - 1)
                queue_list = list(player.queue)
                next_song = queue_list.pop(idx)
                player.queue = deque(queue_list)
            else:
                next_song = player.queue.popleft()

            asyncio.run_coroutine_threadsafe(
                self._start_playback(guild_id, next_song),
                self.bot.loop
            )
        else:
            player.current = None

    async def _start_playback(self, guild_id: int, song: Song):
        player = self.get_player(guild_id)
        player.current = song
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(song.stream_url, **FFMPEG_OPTS),
            volume=player.volume
        )
        player.voice_client.play(source, after=lambda e: self._play_next(guild_id, e))
        if player.text_channel:
            em = song.embed()
            em.set_author(name="🎵 Now Playing")
            await player.text_channel.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # PLAY
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["p"])
    @commands.guild_only()
    async def play(self, ctx, *, query: str):
        """Play a song or add to queue. Supports YouTube / search."""
        if not ctx.author.voice:
            return await ctx.send(embed=error_embed("You need to be in a voice channel."))

        vc = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect()
        elif ctx.author.voice.channel != vc.channel:
            await vc.move_to(ctx.author.voice.channel)

        player = self.get_player(ctx.guild.id)
        player.voice_client = vc
        player.text_channel = ctx.channel

        async with ctx.typing():
            song = await self._fetch_song(query, ctx.author)
        if not song:
            return await ctx.send(embed=error_embed("Couldn't find that song. Try a different query."))

        if vc.is_playing() or vc.is_paused() or player.current:
            player.queue.append(song)
            em = discord.Embed(
                title="Added to Queue",
                description=f"[{song.title}]({song.webpage_url})",
                color=0x1DB954
            )
            em.add_field(name="Duration", value=song.duration_str)
            em.add_field(name="Position", value=str(len(player.queue)))
            em.set_footer(text=f"Requested by {ctx.author}")
            return await ctx.send(embed=em)

        await self._start_playback(ctx.guild.id, song)

    # ─────────────────────────────────────────────────────────────
    # PAUSE / RESUME / STOP
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    async def pause(self, ctx):
        """Pause playback."""
        vc = ctx.voice_client
        if not vc or not vc.is_playing():
            return await ctx.send(embed=warn_embed("Nothing is playing."))
        vc.pause()
        await ctx.send(embed=success_embed("Paused ⏸"))

    @commands.command()
    @commands.guild_only()
    async def resume(self, ctx):
        """Resume paused playback."""
        vc = ctx.voice_client
        if not vc or not vc.is_paused():
            return await ctx.send(embed=warn_embed("Nothing is paused."))
        vc.resume()
        await ctx.send(embed=success_embed("Resumed ▶️"))

    @commands.command()
    @commands.guild_only()
    async def stop(self, ctx):
        """Stop playback and clear the queue."""
        player = self.get_player(ctx.guild.id)
        player.queue.clear()
        player.current = None
        if ctx.voice_client:
            ctx.voice_client.stop()
        await ctx.send(embed=success_embed("Stopped ⏹ and cleared queue."))

    # ─────────────────────────────────────────────────────────────
    # SKIP / SKIPTO
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    async def skip(self, ctx):
        """Skip the current song."""
        vc = ctx.voice_client
        if not vc or not vc.is_playing():
            return await ctx.send(embed=warn_embed("Nothing is playing."))
        vc.stop()
        await ctx.send(embed=success_embed("Skipped ⏭"))

    @commands.command()
    @commands.guild_only()
    async def skipto(self, ctx, position: int):
        """Skip to a position in the queue."""
        player = self.get_player(ctx.guild.id)
        if position < 1 or position > len(player.queue):
            return await ctx.send(embed=error_embed(f"Position must be between 1 and {len(player.queue)}."))
        for _ in range(position - 1):
            player.queue.popleft()
        if ctx.voice_client:
            ctx.voice_client.stop()
        await ctx.send(embed=success_embed(f"Skipped to position #{position}."))

    # ─────────────────────────────────────────────────────────────
    # QUEUE
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["q"])
    @commands.guild_only()
    async def queue(self, ctx, page: int = 1):
        """View the music queue."""
        player = self.get_player(ctx.guild.id)
        if not player.current and not player.queue:
            return await ctx.send(embed=info_embed("Queue is empty."))

        per_page = 10
        pages = max(1, -(-len(player.queue) // per_page))
        page = max(1, min(page, pages))
        start = (page - 1) * per_page

        em = discord.Embed(title="🎵 Music Queue", color=0x1DB954)
        if player.current:
            em.add_field(
                name="Now Playing",
                value=f"[{player.current.title}]({player.current.webpage_url}) `{player.current.duration_str}`",
                inline=False
            )
        queue_list = list(player.queue)[start:start + per_page]
        if queue_list:
            desc = "\n".join(
                f"`{i + start + 1}.` [{s.title}]({s.webpage_url}) `{s.duration_str}` — {s.requester.mention}"
                for i, s in enumerate(queue_list)
            )
            em.add_field(name="Up Next", value=desc, inline=False)
        em.set_footer(text=f"Page {page}/{pages} | {len(player.queue)} songs | Loop: {player.loop}")
        await ctx.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # NP (now playing)
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["nowplaying"])
    @commands.guild_only()
    async def np(self, ctx):
        """Show the currently playing song."""
        player = self.get_player(ctx.guild.id)
        if not player.current:
            return await ctx.send(embed=info_embed("Nothing is playing."))
        em = player.current.embed()
        em.set_author(name="🎵 Now Playing")
        await ctx.send(embed=em)

    # ─────────────────────────────────────────────────────────────
    # VOLUME
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["vol"])
    @commands.guild_only()
    async def volume(self, ctx, vol: int):
        """Set volume (1–150)."""
        if not 1 <= vol <= 150:
            return await ctx.send(embed=error_embed("Volume must be between 1 and 150."))
        player = self.get_player(ctx.guild.id)
        player.volume = vol / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = player.volume
        await ctx.send(embed=success_embed(f"Volume set to **{vol}%** 🔊"))

    # ─────────────────────────────────────────────────────────────
    # LEAVE
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["disconnect", "dc"])
    @commands.guild_only()
    async def leave(self, ctx):
        """Disconnect the bot from voice."""
        if not ctx.voice_client:
            return await ctx.send(embed=warn_embed("I'm not in a voice channel."))
        player = self.get_player(ctx.guild.id)
        player.queue.clear()
        player.current = None
        await ctx.voice_client.disconnect()
        self.players.pop(ctx.guild.id, None)
        await ctx.send(embed=success_embed("Disconnected 👋"))

    # ─────────────────────────────────────────────────────────────
    # REMOVE
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    async def remove(self, ctx, position: int):
        """Remove a song from the queue by position."""
        player = self.get_player(ctx.guild.id)
        if position < 1 or position > len(player.queue):
            return await ctx.send(embed=error_embed(f"Invalid position. Queue has {len(player.queue)} songs."))
        q = list(player.queue)
        removed = q.pop(position - 1)
        player.queue = deque(q)
        await ctx.send(embed=success_embed(f"Removed **{removed.title}** from queue."))

    # ─────────────────────────────────────────────────────────────
    # CLEARQUEUE
    # ─────────────────────────────────────────────────────────────
    @commands.command(aliases=["cq"])
    @commands.guild_only()
    async def clearqueue(self, ctx):
        """Clear the music queue."""
        player = self.get_player(ctx.guild.id)
        player.queue.clear()
        await ctx.send(embed=success_embed("Queue cleared."))

    # ─────────────────────────────────────────────────────────────
    # LOOP
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    async def loop(self, ctx, mode: str = None):
        """Loop: off | song | queue"""
        player = self.get_player(ctx.guild.id)
        modes = ["off", "song", "queue"]
        if mode not in modes:
            next_mode = modes[(modes.index(player.loop) + 1) % len(modes)]
            player.loop = next_mode
        else:
            player.loop = mode
        icons = {"off": "🔁 Off", "song": "🔂 Song", "queue": "🔁 Queue"}
        await ctx.send(embed=success_embed(f"Loop set to **{icons[player.loop]}**."))

    # ─────────────────────────────────────────────────────────────
    # SHUFFLE
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    async def shuffle(self, ctx):
        """Toggle shuffle mode."""
        player = self.get_player(ctx.guild.id)
        player.shuffle_on = not player.shuffle_on
        state = "enabled 🔀" if player.shuffle_on else "disabled"
        await ctx.send(embed=success_embed(f"Shuffle {state}."))

    # ─────────────────────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    async def search(self, ctx, *, query: str):
        """Search YouTube and pick a result to play."""
        async with ctx.typing():
            loop = asyncio.get_event_loop()
            opts = {**YDL_OPTS, "default_search": "ytsearch5", "noplaylist": True}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    data = await loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch5:{query}", download=False))
                results = data.get("entries", [])[:5]
            except Exception:
                return await ctx.send(embed=error_embed("Search failed."))

        if not results:
            return await ctx.send(embed=error_embed("No results found."))

        em = discord.Embed(title=f"Search Results: {query}", color=0x1DB954)
        em.description = "\n".join(
            f"`{i+1}.` [{r['title']}]({r.get('webpage_url','')}) `{int(r.get('duration',0)//60}:{int(r.get('duration',0)%60):02d}`"
            for i, r in enumerate(results)
        )
        em.set_footer(text="Type a number (1-5) to play, or 'cancel'.")
        await ctx.send(embed=em)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and (
                m.content.isdigit() and 1 <= int(m.content) <= len(results)
                or m.content.lower() == "cancel"
            )
        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(embed=warn_embed("Search timed out."))
        if msg.content.lower() == "cancel":
            return await ctx.send(embed=info_embed("Search cancelled."))
        chosen = results[int(msg.content) - 1]
        await ctx.invoke(self.play, query=chosen.get("webpage_url") or chosen.get("url"))

    # ─────────────────────────────────────────────────────────────
    # LYRICS
    # ─────────────────────────────────────────────────────────────
    @commands.command()
    @commands.guild_only()
    async def lyrics(self, ctx, *, query: str = None):
        """Fetch lyrics for a song (or current song)."""
        player = self.get_player(ctx.guild.id)
        if not query:
            if not player.current:
                return await ctx.send(embed=error_embed("Nothing is playing. Provide a song name."))
            query = player.current.title

        genius_key = os.getenv("GENIUS_API_KEY")
        if not genius_key:
            return await ctx.send(embed=error_embed("Genius API key not set in .env."))

        try:
            import lyricsgenius
            genius = lyricsgenius.Genius(genius_key, verbose=False, skip_non_songs=True)
            loop = asyncio.get_event_loop()
            song = await loop.run_in_executor(None, lambda: genius.search_song(query))
        except Exception as e:
            return await ctx.send(embed=error_embed(f"Couldn't fetch lyrics: {e}"))

        if not song:
            return await ctx.send(embed=error_embed(f"No lyrics found for **{query}**."))

        lyrics = song.lyrics[:3900]
        em = discord.Embed(title=f"🎵 {song.title}", description=lyrics, color=0xFFFF00)
        em.set_footer(text=f"By {song.artist} | Via Genius")
        await ctx.send(embed=em)


async def setup(bot):
    await bot.add_cog(Music(bot))
