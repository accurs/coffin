import math

from asyncio import Queue, TimeoutError, gather
from random import shuffle
from async_timeout import timeout

from discord import (
  Embed,
  Guild,
  Member,
  Message,
  TextChannel,
  VoiceState,
)
from discord.ext.commands import (
  BucketType,
  Cog,
  command,
  cooldown,
  has_permissions
)
from typing import (
  TYPE_CHECKING,
  Dict,
  Literal,
  Optional
)
from pomice import (
  Equalizer,
  NodePool,
  Player,
  Playlist,
  Timescale,
  Track,
  SearchType
)
from pomice.exceptions import (
  FilterTagAlreadyInUse,
  NoNodesAvailable,
  TrackLoadError
)
from structure import (
  Percentage,
  Position,
  format_duration,
  shorten,
  Error,
  Coffin,
  Context,
  API
)

if TYPE_CHECKING:
  from discord.abc import MessageableChannel

class _Player(Player):
  bot: "Coffin"

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._queue: Queue[Track] = Queue()
    self._track: Track = None

    self._invoke: MessageableChannel = None
    self._votes = set()

    self._wait: bool = None
    self._person: Member = None

    self._loop: Literal["track", "queue"] = False

  async def add(self: "_Player", track: Track, _push: bool = False) -> Track:
     await (self._queue.put(track) if not _push else self._queue.queue.append(track))
     return track
  
  async def platform_type(self, url: str):
    platform_keywords = {
      "youtube": ["youtube", "youtu.be"],
      "spotify": ["spotify"],
      "soundcloud": ["soundcloud"],
      "apple": ["apple"],
    }
    for platform, keywords in platform_keywords.items():
      if any(keyword in url for keyword in keywords):
        return platform
    
    return "No platform identified"

  async def destroy(self):
    if self.channel:
      await self.bot.session.put(
        f"https://discord.com/api/v9/channels/{self.channel.id}/voice-status",
        headers={"Authorization": f"Bot {self.bot.http.token}"},
        json={"status": None},
      )
      return await super().destroy()

  async def next(self: "_Player") -> Track:
    if self.is_playing or self._wait:
      return

    self._wait = True
    if self._loop == "track" and self._track:
      pass
    else:
      try:
        async with timeout(60):
          self._track = await self._queue.get()
          await self.bot.session.put(
            f"https://discord.com/api/v9/channels/{self.channel.id}/voice-status",
            headers={"Authorization": f"Bot {self.bot.http.token}"},
            json={"status": f"Playing {self._track.title}"},
          )
      except TimeoutError:
        if self.bot.get_channel(self._invoke):
          e = Embed(
            color=self.bot.color,
            description=f"> Left {self.channel.mention if self.channel else 'the voice channel'} due to 1 minute of inactivity",
          )
          await self.bot.get_channel(self._invoke).send(embed=e)
        return await self.destroy()

    self._wait = False
    if self._loop == "queue":
      await self._queue.put(self._track)

    try:
      fetch_song = self.play(self._track)
      fetch_platform = self.platform_type(self._track.uri)
      play, platform = await gather(fetch_song, fetch_platform)

      if self.bot.get_channel(self._invoke) and self._loop != "track":
        emoji = Music(self.bot)._emoji.get(platform, "🎶")
        e = Embed(
          color=self.bot.color,
          description=f"> {emoji} Now playing [**{self._track.title}**]({self._track.uri}) in {self.channel.mention} - {self._track.requester.mention}",
        )
        return await self.bot.get_channel(self._invoke).send(embed=e)

    except TrackLoadError:
      e = Embed(description="> I was unable to find that track!")
      return await self.bot.get_channel(self._invoke).send(embed=e)

  async def skip(self: "_Player") -> Track:
    if self.is_paused:
      await self.set_pause(False)
    return await self.stop()

class Music(Cog):
  """
  Were not lastfm this works
  """
  def __init__(self, bot: Coffin) -> None:
    self.bot: Coffin = bot
    if not self.bot.isinstance:
      self.bot.loop.create_task(self.auth())

    self._emoji: Dict[str, str] = {
      "spotify": "<:spotify:1291029866044461069>",
      "youtube": "<:youtube:1328356883685310555>",
      "apple": "<:apple_music:1328357320610283520>",
      "soundcloud": "<:shazam:1328356576037306491>",
      "discord": "📁",
    }  # Mapping for emojis, useful for filtering.

  async def auth(self: "Music"):
    if not self.bot.node:
      self.bot.node = await NodePool().create_node(
        bot=self.bot,
        host="127.0.0.1",
        port=2333,
        password="youshallnotpass",
        secure=False,
        identifier="COFFIN",
        spotify_client_id=API.sp_id,
        spotify_client_secret=API.sp_secret,
        apple_music=True,
      )
    print(f"Made connection to the node {self.bot.node}")

  async def _votes(self: "Music", ctx: Context) -> int:
    player: _Player = await self.get_player(ctx)
    channel: TextChannel = self.bot.get_channel(int(player.channel.id))
    members = [m for m in channel.members if not m.bot]
    required = math.ceil(len(members) / 2.5)
    
    return max(2, required)

  async def is_person(self: "Music", ctx: Context) -> bool:
    player: _Player = await self.get_player(ctx)
    return (
      ctx.author == player.current.requester
      or ctx.author.guild_permissions.kick_members
      or ctx.author.guild_permissions.administrator
      or ctx.author.id == self.bot.owner_id
    )

  @Cog.listener("on_guild_remove")
  async def guild_remove(self: "Music", guild: Guild):
    if hasattr(self.bot, "node") and self.bot.node is not None:
      player: _Player = getattr(self.bot.node, "get_player", None)
      if player(guild.id):
        await player.destroy()

  @Cog.listener("on_pomice_track_end")
  async def track_end(
    self: "Music", player: _Player, track: Track, reason: str
  ) -> None:
    await player.next()

  @Cog.listener("on_voice_state_update")
  async def track_state(
    self: "Music", member: Member, before: VoiceState, after: VoiceState
  ) -> None:
    if member.id == self.bot.user.id:
      player: _Player = getattr(self.bot.node, "get_player", None)(member.guild.id)
      if not player:
        return

      if before.channel and len(before.channel.members) == 1:
        return (
          await player.destroy()
        )  # leaving if nobody is in the voice channel anymore

      if before.channel and not after.channel:
        voice = self.bot.get_channel(before.channel.id)
        if not voice:
          await player.destroy()
        else:
          channel = self.bot.get_channel(player._invoke)
          await channel.send(
            "I've been kicked or removed from the voice channel!"
          )

      elif before.mute != after.mute:
        await self._handle_mute(player, after.mute)

  async def _handle_mute(self: "Music", player: _Player, muted: bool) -> None:
    await player.set_pause(muted)
    channel = player.guild.get_channel(player._invoke)
    message = (
      f"{'Awesome, I was' if not muted else 'Aww, I have been'} {'muted' if muted else 'unmuted'}. "
      f"I have {'resumed' if not muted else 'paused'} the {'current ' if not muted else ''}song!"
    )
    return await channel.send(message) if muted else await channel.send(message)

  async def get_player(
    self: "Music", ctx: Context, *, connect: bool = False
  ) -> _Player:
    if not hasattr(self.bot, "node"):
      return Error("No connection to the node created!")

    if not (voice := ctx.author.voice):
      return Error("You're not in a voice channel!")

    elif (bot := ctx.guild.me.voice) and (voice.channel.id != bot.channel.id):
      return Error("You're not in my voice channel!")

    if not ctx.guild.me.voice or not (
      player := getattr(self.bot.node, "get_player", None)(ctx.guild.id)
    ):
      if not connect:
        return Error("I'm not connected to a voice channel!")
      
      try:
        await ctx.author.voice.channel.connect(
          cls=_Player, self_deaf=True, reconnect=True
        )
      except NoNodesAvailable:
        return Error("No connection to the node created!")

      player = getattr(self.bot.node, "get_player", None)(ctx.guild.id)
      player._invoke = ctx.channel.id
      player._person = ctx.author
      await player.set_volume(70)

    return player

  @command(
    name="play",
    example="Hospital better off stalking you",
    aliases=["p"],
  )
  @cooldown(1, 3.5, BucketType.user)
  async def play(
    self: "Music", ctx: Context, *, query: Optional[str] = None
  ) -> None:
    """
    Play a song in your voice channel
    """
    player: _Player = await self.get_player(ctx, connect=True)
    # Check if the player is an Error instance before proceeding
    if isinstance(player, Error):
      return await ctx.alert(str(player))  # Display the error message to the user

    if not ctx.message.attachments and not query: 
      return await ctx.send_help(ctx.command)
    
    query = (
      " ".join(attachment.url for attachment in ctx.message.attachments)
      if not query
      else query
    )

    try:
      _result = await player.get_tracks(
        query=query,
        ctx=ctx,
        search_type=SearchType.scsearch,
      )
    except TrackLoadError as e:
      print(e)
      return await ctx.alert("I was unable to find that track!")

    if isinstance(_result, Playlist):
      for track in _result.tracks:
        await player.add(track)

      await ctx.neutral(
        f"Added **{_result.track_count} tracks** from [**{_result.name}**]({_result.uri}) - {_result.tracks[0].requester.mention}!"
      )
    else:
      track = _result[0]
      await player.add(track)
      if player.is_playing:
        await ctx.neutral(
          f"Added [**{track.title}**]({track.uri}) - {track.requester.mention}",
        )

    if not player.is_playing:
      await player.next()
      await ctx.message.add_reaction("✅")

  @command(
    name="current",
    aliases=["playing"],
    description="Shows the currently playing track.",
  )
  async def current(self: "Music", ctx: Context) -> None:
    """
    Check the current playing song
    """
    player: _Player = await self.get_player(ctx)
    loop_status = "**Looping** - " if player._loop else ""

    if not player.current:
      return await ctx.alert("Nothing is currently playing!")

    await ctx.neutral(
      (
        f"{loop_status} Currently playing [**{player.current.title}**]({player.current.uri}) "
        f"in {player.channel.mention} - {player.current.requester.mention} `"
        f"{format_duration(player.position)}`/`{format_duration(player.current.length)}`"
      )
    )

  @command(
    name="shuffle",
    description="Shuffles the track queue.",
  )
  @has_permissions(manage_messages=True)
  async def shuffle(self: "Music", ctx: Context) -> None:
    """
    Shuffle the song queue
    """
    player: _Player = await self.get_player(ctx)
    if not player.current:
      return await ctx.alert("Nothing is currently playing!")

    if not (queue := player._queue._queue):
      return await ctx.alert("The queue is currently empty!")

    shuffle(queue)
    await ctx.confirm("Queue shuffled successfully!")

  @command(
    name="seek",
    example="+30s",
    aliases=["ff", "forward", "rw", "rewind"],
  )
  async def seek(self: "Music", ctx: Context, position: Position) -> None:
    """
    Seek to a specific position in the track
    """
    player: _Player = await self.get_player(ctx)
    if not player.current:
      return await ctx.alert("Nothing is currently playing!")

    if ctx.author.id != player.current.requester.id:
      return await ctx.alert("You can only seek the track you requested.")

    await player.seek(max(0, min(position, player.current.length)))
    await ctx.message.add_reaction("✅")

  @command(
    name="pause",
    aliases=["stop"],
  )
  async def pause(self: "Music", ctx: Context) -> None:
    """
    Pause the current track
    """
    player: _Player = await self.get_player(ctx)
    if player.is_paused:
      return await ctx.alert("There isn't a track playing!")

    await player.set_pause(True)
    await ctx.message.add_reaction("⏸️")

  @command(name="queue", aliases=["q", "tracks"])
  async def queue(self: "Music", ctx: Context) -> None:
    """
    Get the track queue
    """
    player: _Player = await self.get_player(ctx)
    if not (queue := player._queue._queue):
      return await ctx.alert("The queue is currently empty!")

    await ctx.paginate(
      [
        f"[**{shorten(track.title, length=25).replace('[', '(').replace(']', ')')}**]({track.uri}) - Requested by {track.requester.mention}"
        for track in queue
      ],
      Embed(title=f"**Queue for {player.channel.mention}**"),
    )

  @command(name="resume", aliases=["unpause"])
  async def resume(self: "Music", ctx: Context) -> None:
    """
    Resume the current track
    """
    player: _Player = await self.get_player(ctx)
    if not player.is_paused:
      return await ctx.alert("The current track isn't paused!")

    await player.set_pause(False)
    await ctx.message.add_reaction("⏯️")

  @command(
    name="volume",
    example="100%",
    aliases=["vol", "v"],
  )
  async def volume(self: "Music", ctx: Context, volume: Percentage = None) -> Message:
    """
    Change the volume of the player
    """
    player: _Player = await self.get_player(ctx)
    if not player.is_playing:
      return await ctx.alert("There isn't a track currently playing!")

    elif not volume:
      return await ctx.neutral(f"Volume: `{player.volume}%`")

    await player.set_volume(volume)
    await ctx.confirm(f"Set the volume to `{volume}%`")

  @command(name="skip", aliases=["sk", "next"])
  async def skip(self: "Music", ctx: Context) -> None:
    """
    Skip the current track
    """
    player: _Player = await self.get_player(ctx)
    if not player.current:
      return await ctx.alert("Nothing is currently playing!")

    if ctx.author.id == player.current.requester.id:
      await player.skip()
      return await ctx.message.add_reaction("👍")

    required = await self._votes(ctx)
    player._votes.add(ctx.author)

    if len(player._votes) >= required:
      await ctx.send(
        "Vote to skip passed, skipping the current song.", delete_after=10
      )

      player._votes.clear()
      await player.skip()
      await ctx.message.add_reaction("👍")
    else:
      return await ctx.send(
        f"{ctx.author.mention} has voted to skip the song, current amount of votes: {len(player._votes)}/{required} ",
        delete_after=10,
      )

  @command()
  @has_permissions(manage_messages=True)
  async def clearqueue(self: "Music", ctx: Context) -> None:
    """
    Clear the current queue
    """
    player: _Player = await self.get_player(ctx)
    if not self.is_person(ctx):
      return await ctx.alert("Only authorized people can use this command!")

    if not (queue := player._queue._queue):
      return await ctx.alert("The queue is empty!")

    queue.clear()
    await ctx.message.add_reaction("🧹")

  @command(name="loop", aliases=["repeat"])
  async def loop(self: "Music", ctx: Context) -> None:
    """
    Toggle loop the current song
    """
    player: _Player = await self.get_player(ctx)
    if not player.is_playing:
      return await ctx.alert("There isn't a track currently playing!")

    player._loop = False if player._loop == "track" else "track"
    status = "disabled" if player._loop is False else "enabled"

    await ctx.confirm(f"Looping is now **{status}** for the current track.")

  @command(name="move", example="2 1")
  @has_permissions(manage_messages=True)
  async def move(self: "Music", ctx: Context, index: int, new: int) -> Message:
    """
    Move a track from the queue in a different position
    """
    player: _Player = await self.get_player(ctx)
    if not (queue := player._queue._queue):
      return await ctx.alert("The queue is empty!")

    if not (1 <= index <= len(queue)):
      return await ctx.alert(
          f"The index has to be between `1` and `{len(queue)}`!"
      )

    if not (1 <= new <= len(queue)):
      return await ctx.alert(
          f"The new index has to be between `1` and `{len(queue)}`!"
      )

    track = queue[index - 1]
    del queue[index - 1]
    queue.insert(new - 1, track)

    return await ctx.confirm(
      f"Moved [**{track.title}**]({track.uri}) to index `{new}`!"
    )

  @command(name="remove", example="2")
  @has_permissions(manage_messages=True)
  async def remove(self: "Music", ctx: Context, index: int) -> Message:
    """
    Remove a track from the queue
    """
    player: _Player = await self.get_player(ctx)
    if not (queue := player._queue._queue):
      return await ctx.alert("The queue is empty!")

    if not (1 <= index <= len(queue)):
      return await ctx.alert(
          f"The index has to be between `1` and `{len(queue)}`!"
      )

    track = queue[index - 1]
    del queue[index - 1]

    return await ctx.confirm(
      f"Removed [**{track.title}**]({track.uri}) from the queue!"
    )

  @command(
    name="applyfilter", aliases=["af", "ap"], example="boost"
  )
  async def apply_filter(self: "Music", ctx: Context, preset: str):
    """
    Apply a filter to the audio
    """
    if not await self.is_person(ctx):
      return await ctx.alert("You are not authorized to apply filters.")

    valid = {
      "boost": Equalizer.boost(),
      "flat": Equalizer.flat(),
      "metal": Equalizer.metal(),
      "piano": Equalizer.piano(),
      "vaporwave": Timescale.vaporwave(),
      "nightcore": Timescale.nightcore(),
    }
    if preset not in valid:
      return await ctx.alert(
        f"Invalid filter. Available filters: {', '.join([f'`{filter}`' for filter in valid])}"
      )
    try:
      await self.apply_preset(ctx, preset)
      await ctx.confirm(f"Filter `{preset}` applied!")
    except FilterTagAlreadyInUse:
      await ctx.alert(f"Filter `{preset}` already in use!")

  async def apply_preset(self: "Music", ctx: Context, preset: str):
    player: _Player = await self.get_player(ctx)
    mapping = {
      "boost": Equalizer.boost,
      "flat": Equalizer.flat,
      "metal": Equalizer.metal,
      "piano": Equalizer.piano,
      "vaporwave": Timescale.vaporwave,
      "nightcore": Timescale.nightcore,
    }

    method = mapping.get(preset)
    await player.add_filter(method(), fast_apply=True)

  @command(name="resetfilters", aliases=["rf"])
  async def reset_filters(self, ctx: Context):
    """
    Reset the applied filters
    """
    player: _Player = await self.get_player(ctx)
    await player.reset_filters(fast_apply=True)
    await ctx.confirm("All filters reset!")

  @command(name="listfilters", aliases=["filters", "availablefilters"])
  async def list_filters(self: "Music", ctx: Context) -> None:
    """
    List all available filters
    """
    valid = ["boost", "flat", "metal", "piano", "vaporwave", "nightcore"]
    filters = [f"`{filter}`" for filter in valid]
    await ctx.neutral(f"Available filters: {', '.join(filters)}")

  @command(name="disconnect", aliases=["dc"])
  async def disconnect(self: "Music", ctx: Context) -> None:
    """
    Disconenct the bot from the voice channel
    """
    player: _Player = await self.get_player(ctx)
    if isinstance(player, Error):
        return await ctx.alert("You cannot disconnect the bot from the voice channel")

    await player.destroy()
    await ctx.message.add_reaction("👋")

async def setup(bot: Coffin):
  await bot.add_cog(Music(bot))