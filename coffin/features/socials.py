import re
import json 
import asyncio 
import datetime

from collections import defaultdict
from discord.ui import View, Button
from io import BytesIO 
from shazamio import Shazam
from bs4 import BeautifulSoup

from discord import (
  app_commands,
  Embed,
  Color,
  File,
  Member,
  Spotify,
  Attachment,
  Interaction,
  Message
)
from discord.ext.commands import (
  command, 
  hybrid_command, 
  hybrid_group,
  Cog 
)
from typing import (
  Annotated,
  Optional
)
from structure import (
  Coffin,
  ratelimiter,
  Context,
  PaginatorFiles,
  Roblox,
  RobloxUser,
  Snapchat,
  SnapchatUser,
  Tiktok,
  TikTokUser,
  CashApp,
  Telegram,
  TelegramUser,
  SnapchatCelebrity,
  SnapchatStory,
  Pinterest,
  PinterestUser,
  Threads,
  ThreadsUser,
  InstagramUser,
  Instagram,
  Images,
  Brave,
  TwitterUser,
  Twitter
)

class Socials(Cog):
  """
  No platform is safe
  """
  def __init__(self, bot: Coffin):
    self.bot = bot
    self.shazamio = Shazam()
    self.locks = defaultdict(asyncio.Lock)
    self.regex = {
      "pinterest": r"https://((ro|ru|es|uk|fr|de|in|gr|www).pinterest.com/pin|pin.it)/([0-9a-zA-Z]+)",
      "youtube": r"((http(s)?:\/\/)?)(www\.)?((youtube\.com\/)|(youtu.be\/)(watch|shorts))[\S]+",
      "tiktok download": r"^.*https:\/\/(?:m|www|vm|vt)?\.?tiktok\.com\/((?:.*\b(?:(?:v|video|t)\/|\?shareId=|\&item_id=)(\d+))|\w+)",
    }
  
  @Cog.listener("on_message")
  async def on_repost(self: "Socials", message: Message):
    if self.bot.is_ready():
      if message.content.startswith(self.bot.user.name):
        if not ratelimiter(
          bucket=f"reposter-{message.channel.id}",
          key="reposter",
          rate=2,
          per=4,
        ):
          async with self.locks[message.guild.id]:
            ctx = await self.bot.get_context(message)
            url = message.content[len(self.bot.user.name) + 1 :]
            cmd = None

            for name, regex in self.regex.items():
              if re.match(regex, url):
                cmd = self.bot.get_command(name)
                break

            if cmd:
              return await ctx.invoke(cmd, url=url)

  @command()
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def shazam(self, ctx: Context, attachment: Attachment):
    """
    Get the song name from a video
    """
    if not attachment.content_type or not attachment.content_type.startswith("video"):
      return await ctx.alert("This is **not** a video")

    async with ctx.typing():
      try:
        track = await self.shazamio.recognize_song(await attachment.read())
        return await ctx.confirm(
          f"Track: [**{track['track']['share']['subject']}**]({track['track']['share']['href']})"
        )
      except KeyError:
        return await ctx.alert("Unable to find track")

  @command(example="not like us")
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def lyrics(self, ctx: Context, *, song: str):
    """
    Get the lyrics of a song
    """
    x = await self.bot.session.get(f"https://lyrist.vercel.app/api/{song}")
    x.url = f"https://genius.com/{'-'.join(x.artist.split(' '))}-{'-'.join(x.title.split(' '))}-lyrics"
    buffer = BytesIO(bytes(x.lyrics, "utf-8"))
    embed = Embed(title=f"{x.title} by {x.artist}", url=x.url).set_author(
      name=x.artist, icon_url=x.image
    )
    return await ctx.reply(
      embed=embed, 
      file=File(buffer, filename=f"{x.title} lyrics.txt")
    )

  @hybrid_command(aliases=["sp"])
  async def spotify(self, ctx: Context, *, member: Member = None):
    """
    Show what an user is listening on spotify
    """
    if not member:
      member = ctx.author
    a = next((a for a in member.activities if isinstance(a, Spotify)), None)
    if not a:
      return await ctx.alert("You are not listening to **spotify**")
    await ctx.reply(
      f"||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||||​||https://open.spotify.com/track/{a.track_id}"
    )

  @hybrid_command(aliases=["ca"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def cashapp(self, ctx: Context, user: CashApp):
    """
    Get an user's cashapp profile
    """
    embed = (
      Embed(
        color=Color.from_str(user.accent_color),
        title=f"{user.display_name} (@{user.tag})",
        description=f"Donate [${user.tag}]({user.url}) some cash",
        url=user.url,
      )
      .set_thumbnail(url=user.avatar_url)
      .set_image(url=user.qr_url)
    )

    return await ctx.reply(embed=embed)

  @hybrid_command()
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def roblox(self, ctx: Context, user: Annotated[RobloxUser, Roblox]):
    """
    Get information about a roblox user
    """
    embed = (
      Embed(
        color=self.bot.color,
        title=f"@{user.username}",
        url=user.url,
        description=user.bio,
        timestamp=user.created_at,
      )
      .set_thumbnail(url=user.avatar_url)
      .add_field(name="Followers", value=f"{user.followers:,}")
      .add_field(name="Following", value=f"{user.followings:,}")
      .add_field(name="Friends", value=f"{user.friends:,}")
      .set_footer(text=user.id)
    )

    if user.banned:
      embed.add_field(name="banned user")

    return await ctx.reply(embed=embed)

  @hybrid_command(aliases=["yt"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def youtube(self: "Socials", ctx: Context, url: str):
    """
    Repost an youtube video
    """
    yt = re.compile(self.regex["youtube"])
    if not yt.match(url):
      return await ctx.alert("This is **not** an YouTube post url")

    await ctx.typing()
    x = await self.bot.session.post(
      "https://yt5s.io/api/ajaxSearch", data={"q": url, "vt": "mp4"}
    )

    size = next(
      (
        i
        for i in x.links.mp4.values()
        if self.bot.size_to_bytes(i.size)
        < getattr(ctx.guild, "filesize_limit", 26214400)
      ),
      None,
    )

    if not size:
      return await ctx.alert("This video cannot be reposted here")

    async def download():
      z = await self.bot.session.post(
        "https://cv176.ytcdn.app/api/json/convert",
        data={
          "v_id": x["vid"],
          "ftype": size["f"],
          "fquality": size["q"],
          "fname": x["fn"],
          "token": x["token"],
          "timeExpire": x["timeExpires"],
        },
      )
      if z.result == "Converting":
        await asyncio.sleep(1)
        return await download()
      return z.result

    clip = await download()
    buffer = BytesIO(await self.bot.session.get(clip))
    file = File(buffer, filename="youtube.mp4")
    embed = Embed(title=x.title, url=url).set_author(name=x.a)
    return await ctx.reply(embed=embed, file=file)
  
  @hybrid_group(
    aliases=['pin'],
    invoke_without_command=True
  )
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def pinterest(self: "Socials", ctx: Context):
    """
    Scrape information from pinterest
    """
    return await ctx.send_help(ctx.command)
  
  @pinterest.command(name="user")
  async def pinterest_user(
    self: "Socials",
    ctx: Context,
    user: Annotated[PinterestUser, Pinterest]
  ):
    """
    Get information about a pinterest user
    """
    embed = (
      Embed(
        color=self.bot.color,
        title=f"{user.full_name} (@{user.username})",
        url=user.url,
        description=user.about
      )
      .set_thumbnail(
        url=user.profile_picture_url
      )
      .set_author(
        name=", ".join(user.pronouns)
      )
      .add_field(
        name="Boards",
        value=f"{user.boards:,}"
      )
      .add_field(
        name="Followers",
        value=f"{user.followers:,}"
    )
      .add_field(
        name="Following",
        value=f"{user.following:,}"
      )
    )

    return await ctx.reply(embed=embed)

  @pinterest.command(name="download")
  async def pinterest_download(
    self: "Socials", 
    ctx: Context, 
    url: str
  ):
    """
    Repost a pinterest image
    """
    pin = re.compile(self.regex["pinterest"])
    if not pin.match(url):
      return await ctx.alert("This is **not** a pinterest post url")

    html = await self.bot.session.get(url)
    soup = BeautifulSoup(html, "html.parser")

    if not (img := soup.find("img")):
      return await ctx.alert("Image reposting is supported from now")

    data = await self.bot.session.get(img["src"])
    buffer = BytesIO(data)
    return await ctx.reply(
      content=img["alt"], file=File(buffer, filename="pin.jpg")
    )
  
  @hybrid_group(aliases=['snap'], invoke_without_command=True)
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def snapchat(self, ctx: Context):
    """
    Scrape snapchat
    """
    return await ctx.send_help(ctx.command)
    
  @snapchat.command(name="story")
  async def snapchat_story(
    self: "Socials",
    ctx: Context,
    user: Annotated[SnapchatCelebrity, SnapchatStory]
  ):
    """
    Get an user's snapchat stories
    """
    pages = [
      {
        "media_type": story.media_type,
        "media_url": story.media_url,
        "content": f"{story.index+1}/{len(user.stories)} **@{user.username}** \u2022 <t:{story.timestamp}:R>"
      }
      for story in user.stories
    ]
    
    view = PaginatorFiles(ctx, pages)
    await view.start()

  @snapchat.command(name="user")
  async def snapchat_user(
    self: "Socials", 
    ctx: Context, 
    user: Annotated[SnapchatUser, Snapchat]
  ):
    """
    Get information about a snapchat user
    """
    embed = Embed(
      title=f"{user.display_name} ({user.username})", url=user.url
    ).set_thumbnail(url=user.bitmoji)

    kwargs = {"embed": embed}

    if user.snapcode:
      view = View(timeout=None)
      button = Button(
        label=f"Add {user.username}", custom_id="snapchat_user"
      )

      async def callback(interaction: Interaction):
        e = Embed(color=self.bot.color)
        e.set_image(url=user.snapcode)
        return await interaction.response.send_message(embed=e, ephemeral=True)

      button.callback = callback
      view.add_item(button)
      kwargs.update({"view": view})

    return await ctx.reply(**kwargs)

  @hybrid_group(aliases=["tt"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def tiktok(
    self: "Socials",
    ctx: Context,
    user: Optional[Annotated[TikTokUser, Tiktok]] = None,
  ):
    """
    Get information from tiktok
    """
    if not user:
      return await ctx.send_help(ctx.command)
    else:
      return await ctx.invoke(self.bot.get_command("tiktok user"), user=user)

  @tiktok.command(name="user")
  async def tiktok_user(
    self: "Socials", 
    ctx: Context, 
    user: Annotated[TikTokUser, Tiktok]
  ):
    """
    Get information about a tiktok user
    """
    embed = (
      Embed(
        color=self.bot.color,
        title=f"@{user.username}",
        url=user.url,
        description=user.bio,
      )
      .set_thumbnail(url=user.avatar)
      .add_field(name="Followers", value=f"{user.followers:,}")
      .add_field(name="Following", value=f"{user.following:,}")
      .add_field(name="Hearts", value=f"{user.hearts:,}")
    )

    return await ctx.reply(embed=embed)

  @tiktok.command(name="download", aliases=["dl"])
  async def tiktok_download(self: "Socials", ctx: Context, url: str):
    """
    Repost a tiktok video
    """
    tt = re.compile(self.regex["tiktok download"])
    if not tt.match(url):
      return await ctx.alert("This is not a **TikTok** post url")

    await ctx.typing()
    headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0"
    }

    html = await self.bot.session.get(url, headers=headers)
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", attrs={"id": "__UNIVERSAL_DATA_FOR_REHYDRATION__"})
    payload = json.loads(script.text)

    if not payload["__DEFAULT_SCOPE__"].get("webapp.video-detail"):
      return await ctx.alert("This tiktok cannot be downloaded now")

    video_info = payload["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"][
      "itemStruct"
    ]

    video_url = video_info["video"]["playAddr"]
    b = await self.bot.session.get(video_url, headers=headers)

    if len(b) > getattr(ctx.guild, "filesize_limit", 26214400):
      return await ctx.alert("Cannot download this video here")

    file = File(BytesIO(b), filename="tiktok.mp4")

    desc = video_info["desc"]
    created_at = datetime.datetime.fromtimestamp(int(video_info["createTime"]))

    author = {
      "name": video_info["author"]["uniqueId"],
      "icon_url": video_info["author"]["avatarLarger"],
    }

    likes = video_info["stats"]["diggCount"]
    embed = (
      Embed(
        description=f"[{desc}]({url})" if desc != "" else None,
        timestamp=created_at,
      )
      .set_author(**author)
      .set_footer(text=f"{likes:,} ❤️")
    )
    return await ctx.reply(embed=embed, file=file)

  @hybrid_command()
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def threads(
    self, 
    ctx: Context, 
    user: Annotated[ThreadsUser, Threads]
  ):
    """
    Look up for a threads user
    """
    embed = (
      Embed(
        color=self.bot.color,
        title=user.title,
        url=user.url,
        description=user.bio
      )
      .set_thumbnail(
        url=user.profile_pic
      )
    )

    return await ctx.send(embed=embed) 

  @hybrid_command(aliases=["ig"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def instagram(
    self, 
    ctx: Context, 
    user: Annotated[InstagramUser, Instagram]
  ):
    """
    Look up for an instagram profile
    """
    badges = [
      "🔒" if user.is_private else "",
      "<:verified:1271547192485871717>" if user.is_verified else ""
    ]
    biolinks = [f"{name} - {url}" for name, url in user.biolinks.items()]

    embed = (
      Embed(
        title=f"@{user.username} {''.join(filter(None, badges))}",
        url=user.url,
        description=user.bio,
      )
      .set_thumbnail(url=user.avatar_url)
      .set_author(name=", ".join(user.pronouns))
      .add_field(name="Posts", value=f"{user.posts:,}")
      .add_field(name="Followers", value=f"{user.followers:,}")
      .add_field(name="Following", value=f"{user.following:,}")
    )

    view = None
    if biolinks:
      view = View()
      button = Button(label="Biolinks")

      async def callback(interaction: Interaction):
        e = (
          Embed(
            color=self.bot.color,
            title=f"@{user.username} biolinks",
            description="\n".join(biolinks),
            url=user.url,
          )
          .set_thumbnail(url=user.avatar_url)
        )

        return await interaction.response.send_message(embed=e, ephemeral=True)

      button.callback = callback
      view.add_item(button)

    return await ctx.reply(embed=embed, view=view)
  
  @hybrid_command(aliases=["x"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def twitter(
    self, 
    ctx: Context,
    user: Annotated[TwitterUser, Twitter]
  ):
    """
    Look up for a twitter profile
    """
    embed = (
      Embed(
        color=self.bot.color,
        title=f"{user.display_name} (@{user.username})",
        url=user.url,
        description=user.bio
      )
      .set_thumbnail(url=user.avatar)
      .set_author(
        name=ctx.author.name,
        icon_url=ctx.author.display_avatar.url
      )
      .add_field(name="Posts", value=f"{user.posts:,}")
      .add_field(name="Followers", value=f"{user.followers:,}")
      .add_field(name="Following", value=f"{user.following:,}")
    )
    await ctx.reply(embed=embed)

  @hybrid_command(aliases=["img"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def image(
    self,
    ctx: Context,
    *,
    query: Annotated[Images, Brave]
  ):
    """
    Search for an image on the web
    """
    embeds = [
      Embed(
        color=self.bot.color, 
        title=f"Result for {query.query}"
      ).set_image(url=image)
      for image in query.images
    ]
    await ctx.paginate(embeds)
  
  @hybrid_command(aliases=['tg'])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def telegram(self, ctx: Context, user: Annotated[TelegramUser, Telegram]):
    """
    Get information about a telegram user
    """
    embed = (
      Embed(
        color=0x229ED9,
        title=f"{user.display_name} (@{user.username})",
        url=user.url,
        description=user.bio
      )
      .set_thumbnail(
        url=str(user.profile_pic) if user.profile_pic else None
      )
      .set_author(
        name=ctx.author.name,
        icon_url=ctx.author.display_avatar.url
      )
    )

    return await ctx.reply(embed=embed)

  @hybrid_command(aliases=["gh"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def github(self, ctx: Context, user: str):
    """
    Get info about a github account
    """
    data = await self.bot.session.get(f"https://api.github.com/users/{user}")
    avatar = data["avatar_url"]
    url = data["html_url"]
    name = data["name"]
    company = data["company"]
    location = data["location"]
    biotext = data["bio"]
    followers = data["followers"]
    following = data["following"]
    repos = data["public_repos"]

    embed = Embed(
      title=f"{name} (@{user})",
      url=url,
      description=f"> {biotext}" if biotext else "",
      color=0x31333B,
    )
    embed.set_thumbnail(url=avatar if avatar else "https://none.none")
    embed.add_field(name="company", value=company, inline=True)
    embed.add_field(name="location", value=location, inline=True)
    embed.add_field(name="repo count", value=repos, inline=True)
    embed.set_footer(text=f"followers: {followers} | following: {following}")

    await ctx.send(embed=embed)

async def setup(bot: Coffin):
  await bot.add_cog(Socials(bot))