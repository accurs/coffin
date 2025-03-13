import asyncio
import os
import uwuify

from collections import defaultdict

from discord import (
  Attachment,
  Colour,
  File,
  HTTPException,
  Member,
  Message
)
from discord.ext.commands import (
  Cog,
  command,
  group,
  has_permissions,
  is_donator
)
from structure import (
  Coffin,
  Context,
  Color,
  ratelimiter
)
from typing import (
  Annotated,
  Union
)

class Premium(Cog):
  """
  U neda be rich like i am
  """
  def __init__(self, bot: Coffin):
    self.bot = bot
    self.locks = defaultdict(asyncio.Lock)

  async def cog_check(self, ctx: Context) -> bool:
    return await is_donator().predicate(ctx)
  
  @Cog.listener("on_message")
  async def uwulocked(self, message: Message):
    if (
      message.guild and
      not message.author.bot and
      await self.bot.db.fetchval(
       "SELECT EXISTS(SELECT 1 FROM uwulock WHERE guild_id = $1 AND user_id = $2)",
        message.guild.id,
        message.author.id
      )
    ):
      if not ratelimiter(
        bucket=f"uwulock-{message.guild.id}", key="uwulock", rate=9, per=10
      ):
        flags = uwuify.YU | uwuify.STUTTER
        content = uwuify.uwu(message.content, flags=flags)
        await message.delete()

        try:
          webhook = next(
            (
              w
              for w in await message.channel.webhooks()
              if w.user.id == self.bot.user.id
            ),
          )
        except StopIteration:
          webhook = await message.channel.create_webhook(
            name=f"{self.bot.user.name} - uwulock"
          )
          
        await webhook.send(
          content=content,
          avatar_url=message.author.display_avatar.url,
          username=message.author.name
        )
  
  @command()
  @has_permissions(manage_messages=True)
  async def uwulock(self: "Premium", ctx: Context, *, member: Member):
    """
    Uwulock a member messages
    """
    if await self.bot.db.fetchrow(
      "SELECT * FROM uwulock WHERE guild_id = $1 AND user_id = $2",
      ctx.guild.id,
      member.id
    ):
      await self.bot.db.execute(
        "DELETE FROM uwulock WHERE guild_id = $1 AND user_id = $2",
        ctx.guild.id,
        member.id
      )
      return await ctx.message.add_reaction("👍")
    else:
      await self.bot.db.execute(
        "INSERT INTO uwulock VALUES ($1,$2)",
        ctx.guild.id,
        member.id
      )
      return await ctx.message.add_reaction("👍")

  @command()
  async def makemp3(self, ctx: Context, video: Attachment):
    """
    Convert video to mp3
    """
    if not video.content_type or not video.content_type.startswith("video"):
      return await ctx.alert("Attachment must be a video")

    if video.size > 10000000:
      return await ctx.alert("Max file size must be `10 MB`")

    async with ctx.typing():
      async with self.locks[video.filename]:
        path = f"./{video.filename}"
        path2 = f"./{video.filename[:-3]}mp3"
        await video.save(path)
        os.system(f"ffmpeg -i {path} {path2}")

        try:
          return await ctx.reply(file=File(path2))
        except HTTPException:
          return await ctx.alert("File too large")
        finally:
            os.remove(path)
            os.remove(path2)

  @command(aliases=["vid2gif"])
  async def videotogif(self, ctx: Context, video: Attachment):
    """
    Convert a video to gif
    """
    if not video.content_type or not video.content_type.startswith("video"):
      return await ctx.alert("Attachment must be a video")

    if video.size > 10000000:
      return await ctx.alert("Max file size must be `10 MB`")

    async with ctx.typing():
      async with self.locks[video.filename]:
        path = f"./{video.filename}"
        path2 = f"./{video.filename[:-3]}gif"
        await video.save(path)
        os.system(f"ffmpeg -i {path} {path2}")

        try:
          return await ctx.reply(file=File(path2))
        except HTTPException:
          return await ctx.alert("File too large")
        finally:
            os.remove(path)
            os.remove(path2)

  @group(invoke_without_command=True)
  async def reskin(self, ctx: Context):
    """
    Customize the bot's appearance
    """
    return await ctx.send_help(ctx.command)

  @reskin.command(name="color", aliases=["colour"])
  async def reskin_color(
    self, ctx: Context, color: Union[Annotated[Colour, Color], str]
  ):
    """
    Change the bot's color
    """
    if isinstance(color, str):
      if color.lower() == "none":
        value = None
      else:
        return await ctx.send_help(ctx.command)
    else:
      value = color.value

    await self.bot.db.execute(
      """
      INSERT INTO reskin (user_id, color) VALUES ($1,$2)
      ON CONFLICT (user_id) DO UPDATE SET color = $2
      """,
      ctx.author.id,
      value,
    )

    return await ctx.confirm(f"Updated the reskin's color to `{color if value else 'default'}`")

  @reskin.command(name="delete", aliases=["del", "rem", "remove", "rm"])
  async def reskin_delete(self, ctx: Context):
    """
    Delete your own custom bot appearance
    """
    r = await self.bot.db.execute(
      "DELETE FROM reskin WHERE user_id = $1", ctx.author.id
    )
    if r == "DELETE 0":
      return await ctx.alert("You do not have a reskin")

    return await ctx.confirm("Deleted your reskin")

  @reskin.command(name="copy")
  async def reskin_copy(self, ctx: Context, *, member: Member):
    """
    Copy someone else's bot appearance
    """
    results = await self.bot.db.fetchrow(
      "SELECT username, avatar_url, color FROM reskin WHERE user_id = $1",
      member.id,
    )
    if not results:
      return await ctx.alert("This member does not have a reskin")

    await self.bot.db.execute(
      """
      INSERT INTO reskin VALUES ($1,$2,$3,$4)
      ON CONFLICT (user_id) DO UPDATE SET
      username = $2, avatar_url = $3, color = $4  
      """,
      ctx.author.id,
      *results,
    )

    return await ctx.confirm(f"Copied {member.mention}'s reskin")

  @reskin.command(name="avatar", aliases=["av", "icon", "pfp"])
  async def reskin_avatar(self, ctx: Context, avatar: Attachment):
    """
    Change the bot's avatar with an attachment
    """
    if not avatar.content_type or not avatar.content_type.startswith("image"):
      return await ctx.alert("This is not a valid attachment for an avatar")
    
    r = await self.bot.session.post(
      "https://api.coffin.lol/upload",
      params={"url": avatar.url, "type": "reskin"}
    )

    await self.bot.db.execute(
      """
      INSERT INTO reskin (user_id, avatar_url) VALUES ($1,$2)
      ON CONFLICT (user_id) DO UPDATE SET avatar_url = $2  
      """,
      ctx.author.id,
      r.url,
    )

    return await ctx.confirm("Updated your reskin's avatar")

  @reskin.command(name="name", aliases=["username"])
  async def reskin_name(self, ctx: Context, *, name: str):
    """
    Edit the bot's name
    """
    if name.lower() == "none":
      name = None

    await self.bot.db.execute(
      """
      INSERT INTO reskin (user_id, username) VALUES ($1,$2)
      ON CONFLICT (user_id) DO UPDATE SET username = $2    
      """,
      ctx.author.id,
      name,
    )

    return await ctx.confirm(f"Updated your reskin username to: **{name or self.bot.user.name}**")

async def setup(bot: Coffin) -> None:
  return await bot.add_cog(Premium(bot))