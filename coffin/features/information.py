import humanize
import psutil

from io import BytesIO
from typing import Union
from time import perf_counter
from contextlib import suppress
from discord.abc import GuildChannel
from discord.ui import Button, View
from discord.utils import format_dt, oauth_url, utcnow
from structure.managers.discordstatus import DiscordStatus
from jishaku.math import natural_size, mean_stddev

from discord import (
  ButtonStyle,
  Embed,
  Attachment,
  File,
  Member,
  Message,
  Permissions,
  Role,
  User,
  Invite,
  Object,
  __version__,
  app_commands,
)
from typing import (
  Optional,
  List
)
from discord.ext.commands import (
  Author,
  Cog,
  command,
  has_permissions,
  hybrid_command
)
from structure import (
  Coffin,
  Context,
  COFFIN
)

class Information(Cog):
  """
  Self explanatory bros
  """
  def __init__(self, bot: Coffin):
    self.bot: Coffin = bot

  @hybrid_command()
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def status(self: "Information", ctx: Context):
    """
    Get discord statuses
    """
    data = await DiscordStatus.from_response()
    embed = data.to_embed(self.bot, False)
    return await ctx.send(embed=embed)

  @command()
  async def donate(
    self: "Information", 
    ctx: Context
  ) -> Message:
    """
    Donate to coffin
    """
    await ctx.send(embed=Embed(color=self.bot.color, title="coffin — donate", description=f">>> LTC: `LLcWDBf7SkiES7m5F1Y8WR9ZftBEzA7XAs`\nBTC: `bc1qgydcnwzvar6hp3z4nng4kge06x8jxfrm965m3f`\nCashApp: [`$nycsluts`](<https://cash.app/$nycsluts>)\nOr boost our [**`support server`**]({COFFIN.SUPPORT_URL})"))

  @command()
  async def perks(
    self: "Information", 
    ctx: Context
  ) -> Message:
    """
    Features u get access after buying premium
    """
    await ctx.send(
      embed=Embed(
        color=self.bot.color,
        title="coffin — perks",
        description=f">>> {', '.join(map(lambda c: c.qualified_name, self.bot.get_cog('Premium').get_commands()))}\n+20% more credits and +4xp for level\nmore coming soon, give ideas in our [support server]({COFFIN.SUPPORT_URL})"
      )
    )

  @hybrid_command(name="ping", aliases=["latency"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def ping(self: "Information", ctx: Context) -> Message:
    """
    Get the bot's latency
    """
    return await ctx.reply(f"... `{round(self.bot.latency * 1000)}ms`")

  @command(aliases=["discord"])
  async def support(self, ctx: Context) -> Message:
    """
    Get an invite link for the bot's support server.
    """
    return await ctx.reply(COFFIN.SUPPORT_URL)
      
  @hybrid_command(aliases=["creds", "devs", "developers" "dev"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def credits(self: "Information", ctx: Context):
    """
    Get credits on the bot's contributor's team
    """
    embed = (
    Embed(
      color=self.bot.color,
    )
    .set_footer(text=f"{self.bot.user.name} credits • coffin.lol")
    .set_thumbnail(url=self.bot.user.avatar)
    )
    embed.add_field(
      name="Credits",
      value='\n'.join(
        [
          f"`{i}.` **{self.bot.get_user(user_id)}** - {'Founder' if user_id == 628236220392275969 else 'Owner'} & Developer (`{user_id}`)" 
          for i, user_id in enumerate(self.bot.owner_ids, start=1)
        ]
      )
    )
    view = View().add_item(
    Button(style=ButtonStyle.grey, label="owners", disabled=True)
    )
    await ctx.reply(embed=embed, view=view)

  @hybrid_command(aliases=["bi", "bot", "info", "about"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def botinfo(self: "Information", ctx: Context):
    """
    Get info on bot
    """
    embed = (
      Embed(
        color=self.bot.color,
        description=f"Maintained and Developed by [**coffin team**]({COFFIN.SUPPORT_URL})\nServing `{len(self.bot.users):,}` user(s) in over `{len(self.bot.guilds):,}` guild(s)"
      )
      .set_author(
        name=self.bot.user.name,
        icon_url=self.bot.user.display_avatar.url
      )
      .add_field(
        name="Statistics",
        value=f"commands: `{len(set(self.bot.walk_commands()))}`\nlatency: `{round(self.bot.latency * 1000)}ms`\ncreated: {format_dt(self.bot.user.created_at, style='R')}"
      )
      .add_field(
        name="Backend",
        value=f"lines: `{self.bot.lines:,}`\nfiles: `{len(self.bot.files):,}`\nstarted: {format_dt(self.bot.uptime, style='R')}"
      )
    )
    
    if psutil:
      with suppress(psutil.AccessDenied):
        proc = psutil.Process()

        with proc.oneshot():
          mem = proc.memory_full_info()
          cpu = proc.cpu_percent()
          embed.set_footer(
            text=f"Memory: {natural_size(mem.rss)} {psutil.virtual_memory().percent}% on discord.py{__version__}"
          )
    return await ctx.reply(embed=embed)

  @hybrid_command(aliases=["hex"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def dominant(self: "Information", ctx: Context, *, attachment: Attachment):
    """
    Get the dominant color of an image
    """
    if not attachment.content_type.startswith("image"):
      return await ctx.alert("This is not an image")

    color = hex(await ctx.dominant(attachment.read()))[2:]
    hex_info = await self.bot.session.get("https://www.thecolorapi.com/id", params={"hex": color})
    hex_image = f"https://singlecolorimage.com/get/{color}/200x200"
  
    embed = (
      Embed(
      color=int(color, 16)
      )
      .set_author(
        name=hex_info["name"]["value"],
        icon_url=hex_image
      )
      .set_thumbnail(
        url=hex_image
      )
      .add_field(
        name="RGB",
        value=hex_info["rgb"]["value"]
      )
      .add_field(
        name="HEX",
        value=hex_info["hex"]["value"]
      )
    )
    await ctx.reply(embed=embed)
          
  @command()
  @has_permissions(view_audit_log=True)
  async def audit(self, ctx: Context):
    """
    View the audit log
    """
    def format_action(action: str):
      if action == "kick":
        return "kicked"
      
      arr = action.split('_')
      if arr[-1].endswith('e'):
        return f"{arr[-1]}d {' '.join(arr[:-1])}"
      elif arr[-1].endswith('n'):
        if len(arr) == 1:
          return f"{arr[0]}ned"
        else:
          return f"{arr[-1]}ned {' '.join(arr[:-1])}"
      else:
        return f"{arr[-1]} {' '.join(arr[:-1])}"
    
    def format_object(target):
      if isinstance(target, (Member, User)):
        return f"[@{target.name}]({target.url})"
      
      elif isinstance(target, GuildChannel):
        return f"[#{target.name}]({target.jump_url})"
      
      elif isinstance(target, Role):
        return f"@{target.name}"
      
      elif isinstance(target, Invite):
        return f"[{target.code}]({target.url})"
      
      elif isinstance(target, Object):
        if target.type == Role:
          return f"{f'@{ctx.guild.get_role(target.id).name}' if ctx.guild.get_role(target.id) else f'**{target.id}**'}"
        else:
          return f"**{target.id}**"

    logs = [
      entry async for entry in ctx.guild.audit_logs() 
      if 'automod' not in entry.action.name
    ]
    return await ctx.paginate(
      [
        f"[@{entry.user.name}]({entry.user.url}) {format_action(entry.action.name)} {format_object(entry.target)}"
        for entry in logs
      ],
      Embed(title="Audit Log")
    )

  @hybrid_command()
  @has_permissions(ban_members=True)
  async def bans(self: "Information", ctx: Context) -> Message:
    """
    View all bans
    """
    bans = [entry async for entry in ctx.guild.bans()]

    if not bans:
      return await ctx.alert("No bans found in this server")

    return await ctx.paginate(
      [
        f"{entry.user} ({entry.user.id}) - {entry.reason or 'No reason provided'}"
        for entry in bans
      ],
      Embed(title=f"Bans in {ctx.guild} ({len(bans)})"),
    )
  
  @hybrid_command()
  async def boosters(
    self: "Information",
    ctx: Context
  ):
    """
    View all boosters
    """
    if not (
      boosters := [
        member for member in ctx.guild.members 
        if member.premium_since
      ]
    ):
      return await ctx.alert("There are no boosters in this server")
    
    return await ctx.paginate(
      [
        f"{member.mention} {format_dt(member.premium_since, style='R')}"
        for member in boosters
      ],
      Embed(title="Server boosters")
    )

  @hybrid_command()
  async def bots(
    self: "Information",
    ctx: Context,
  ) -> Message:
    """
    View all bots
    """
    if not (
      bots := filter(
        lambda member: member.bot,
        ctx.guild.members,
      )
    ):
      return await ctx.alert(f"No bots have been found in {ctx.guild.name}!")

    return await ctx.paginate(
      [f"{bot.mention}" for bot in bots], Embed(title=f"Bots in {ctx.guild.name}")
    )

  @hybrid_command(name="members", aliases=["inrole"])
  async def members(
    self: "Information", ctx: Context, *, role: Role = None
  ) -> Message:
    """
    View all members in a role
    """
    role = role or ctx.author.top_role

    if not role.members:
      return await ctx.alert(f"No members in the role {role.mention}!")

    return await ctx.paginate(
      [f"{user.mention}" for user in role.members],
      Embed(title=f"Members in {role.name}"),
    )

  @hybrid_command(name="roles")
  async def roles(
    self: "Information",
    ctx: Context,
  ) -> Message:
    """
    View all roles
    """
    if not (roles := reversed(ctx.guild.roles[1:])):
      return await ctx.alert(f"No roles have been found in {ctx.guild.name}!")

    return await ctx.paginate(
      [f"{role.mention}" for role in roles],
      Embed(title=f"Roles in {ctx.guild.name}"),
    )

  @hybrid_command(name="emojis", aliases=["emotes"])
  async def emojis(
    self: "Information",
    ctx: Context,
  ) -> Message:
    """
    View all emojis
    """
    if not ctx.guild.emojis:
      return await ctx.alert(f"No emojis have been found in {ctx.guild.name}!")

    return await ctx.paginate(
      [f"{emoji} [`{emoji.name}`]({emoji.url})" for emoji in ctx.guild.emojis],
      Embed(title=f"Emojis in {ctx.guild.name}"),
    )

  @command(name="stickers")
  async def stickers(
    self: "Information",
    ctx: Context,
  ) -> Message:
    """
    View all stickers
    """
    if not ctx.guild.stickers:
      return await ctx.alert(f"No stickers have been found in {ctx.guild.name}!")

    return await ctx.paginate(
      [f"[`{sticker.name}`]({sticker.url})" for sticker in ctx.guild.stickers],
      Embed(title=f"Stickers in {ctx.guild.name}"),
    )

  @command(name="invites")
  async def invites(
    self: "Information",
    ctx: Context,
    *,
    user: Optional[Member] = None
  ) -> Message:
    """
    View all invites
    """
    if user:
      return await ctx.reply(embed=Embed(description=f"{user.mention} has **{sum(invite.uses for invite in await ctx.guild.invites() if invite.inviter.id == user.id)}** invites"))

    if not (
      invites := sorted(
        [invite for invite in await ctx.guild.invites() if invite.expires_at],
        key=lambda invite: invite.expires_at,
        reverse=True,
      )
    ):
      return await ctx.alert(f"No invites have been found in {ctx.guild.name}!")

    return await ctx.paginate(
      [
        (
          f"[`{invite.code}`]({invite.url}) expires "
          + format_dt(
            invite.expires_at,
            style="R",
          )
        )
        for invite in invites
      ],
      Embed(title=f"Invite in {ctx.guild.name}"),
    )

  @hybrid_command(name="avatar", aliases=["av", "pfp"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def avatar(
    self: "Information",
    ctx: Context,
    *,
    user: Union[Member, User] = Author
  ) -> Message:
    """
    View a users avatar
    """
    view = View()
    [
      view.add_item(
        Button(
          style=ButtonStyle.link,
          label=f.upper(),
          url=str(user.display_avatar.replace(size=4096, format=f))
        )
      )
      for f in ['png', 'jpg', 'webp']
    ]
    
    embed = (
      Embed(
        title=f"{user.name}'s avatar",
        description=f"[Click here to download]({user.display_avatar})",
        url=user.display_avatar
      )
      .set_image(url=user.display_avatar.url)
    )
    
    return await ctx.send(embed=embed, view=view)

  @command(name="banner", aliases=["ub", "userbanner"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def banner(
    self: "Information", 
    ctx: Context, 
    *, 
    member: Union[Member, User] = Author
  ) -> Message:
    """
    View a users banner
    """
    user = await self.bot.fetch_user(member.id)

    if not user.banner:
      return await ctx.alert(
        "You don't have a banner set!"
        if user == ctx.author
        else f"{user} does not have a banner set!"
      )

    embed = Embed(title=f">>> {user.name}'s banner").set_image(url=user.banner)
    return await ctx.send(embed=embed)

  @hybrid_command(name="invite", aliases=["inv", "getbotinvite"])
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def invite(self: "Information", ctx: Context, user: Optional[User] = None):
    """
    Get the invite for coffin
    """
    if user and not user.bot:
      return await ctx.alert("This is not a bot.")

    invite_url = oauth_url(
    getattr(user, "id", self.bot.user.id),
    permissions=Permissions(permissions=8),
    )
    return await ctx.reply(invite_url)
      
  @hybrid_command(
    name="uptime",
    aliases=["ut", "up"],
  )
  @app_commands.allowed_installs(guilds=True, users=True)
  @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def uptime(self: "Information", ctx: Context) -> Message:
    """
    View the bot's uptime
    """
    return await ctx.reply(
      embed=Embed(
        description=f"⏰ **{self.bot.user.display_name}** has been up for: {humanize.precisedelta(utcnow() - self.bot.uptime, format='%0.0f')}"
      )
    )

  @command(name="itemshop", aliases=["fnshop"])
  async def fortnite_shop(self: "Information", ctx: Context) -> Message:
    """
    View the Fortnite item shop
    """
    buffer = await self.bot.session.get(
      f"https://bot.fnbr.co/shop-image/fnbr-shop-{utcnow().strftime('%-d-%-m-%Y')}.png"
    )
    return await ctx.send(file=File(BytesIO(buffer), filename="shop.png"))

  @hybrid_command(aliases=["mc"])
  async def membercount(self, ctx: Context):
    """
    Get the amount of members in this server
    """
    users = [m for m in ctx.guild.members if not m.bot]
    bots = [m for m in ctx.guild.members if m.bot]

    percentage = lambda a: round((a / ctx.guild.member_count) * 100, 2)  # noqa: E731

    embed = Embed(
      description="\n".join(
        (
          f"**members:** `{ctx.guild.member_count:,}`",
          f"**users:**: `{len(users):,}` ({percentage(len(users))}%)",
          f"**bots:** `{len(bots):,}` ({percentage(len(bots))}%)",
        )
      )
    )

    new_joined = sorted(
      filter(
        lambda m: (utcnow() - m.joined_at).total_seconds() < 600,
        ctx.guild.members,
      ),
      key=lambda m: m.joined_at,
      reverse=True,
    )

    if new_joined:
      embed.add_field(
        name=f"New members ({len(new_joined)})",
        value=(
          ", ".join(map(str, new_joined[:5]))
          + f" + {len(new_joined)-5} more"
          if len(new_joined) > 5
          else ""
        ),
        inline=False,
      )

    return await ctx.reply(embed=embed)

async def setup(bot: Coffin) -> None:
  return await bot.add_cog(Information(bot))