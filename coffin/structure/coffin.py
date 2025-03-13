import asyncio
import json
import math
import os
import random
import re
import humanize
import parsedatetime as pdt
import discord_ios  # noqa: F401

from humanize import precisedelta
from collections import defaultdict
from bs4 import BeautifulSoup
from contextlib import suppress
from datetime import datetime
from datetime import timezone as date_timezone
from io import BytesIO
from os import environ
from pathlib import Path
from aiohttp.client_exceptions import ClientConnectorError, ClientResponseError
from nudenet import NudeDetector
from pomice import Node
from pyppeteer import launch
from pytz import timezone
from functools import cached_property
from hashlib import sha256, md5

from discord import (
  AllowedMentions,
  CustomActivity,
  Embed,
  File,
  Guild,
  Intents,
  Interaction,
  Member,
  Message,
  Permissions,
  Status,
  User,
  NotFound
)
from discord.app_commands.errors import CommandInvokeError
from discord.ext import tasks
from discord.utils import format_dt, oauth_url, utcnow
from discord.ext.commands import (
  AutoShardedBot,
  BadArgument,
  BadLiteralArgument,
  CheckFailure,
  CommandError,
  CommandNotFound,
  CommandOnCooldown,
  MissingPermissions,
  MissingRequiredArgument,
  MissingRequiredAttachment,
  MissingRequiredFlag,
  NotOwner,
  UserInputError,
  when_mentioned_or
)

from structure.config import (
  API,
  COFFIN,
  ShardStatus
)
from structure.managers import (
  Cache,
  ClientSession,
  Context,
  Help,
  Workers,
  database,
  getLogger,
  ratelimiter
)
from structure.patcher import cmds, inter, member, server  # noqa: F401
from structure.utilities import (
  Embed as ScriptedEmbed,
  Afk,
  ApplicationInfo,
  ApplicationLegal,
  Error,
  Giveaway,
  Proxy,
  TicketClose,
  TicketView,
  VoiceMasterView,
)
from typing import (
  List,
  Optional,
  Union
)

logger = getLogger(__name__)

with open(os.path.expanduser("./.env")) as env_file:
  for line in env_file:
    if len(line) > 0:
      lhs = line.split("=")[0]
      rhs = line.split("=")[1]
      os.environ[lhs]=rhs.strip()

environ.update(
  {
    "JISHAKU_HIDE": "True",
    "JISHAKU_RETAIN": "True",
    "JISHAKU_NO_UNDERSCORE": "True",
    "JISHAKU_SHELL_NO_DM_TRACEBACK": "True",
    "JISHAKU_NO_DM_TRACEBACK": "True",
    "JISHAKU_FORCE_PAGINATOR": "True"
  }
)

class Coffin(AutoShardedBot):
  def __init__(
    self: "Coffin",
    instance_owner_id: int = 1,
    color: Optional[int] = None,
    node: Optional[Node] = None,
    instance: bool = False,
    dbname: str = "postgres",
    status: Status = Status.online,
    activity: Optional[CustomActivity] = CustomActivity(name="🔗 discord.gg/sore"),
  ):
    super().__init__(
      shard_count=COFFIN.shards,
      description="feature-rich",
      help_command=Help(),
      command_prefix=bot_prefix,
      intents=Intents.all(),
      case_insensitive=True,
      strip_after_prefix=True,
      owner_ids=COFFIN.owners,
      allowed_mentions=AllowedMentions(
        replied_user=False,
        everyone=False,
        roles=False,
      ),
      status=status,
      activity=activity,
    )
    self.uptime: datetime = utcnow()
    self.browser = None
    self.dbname = dbname
    self.isinstance = instance
    self.logger = logger
    self.node: Node = node
    self.instance_owner_id = instance_owner_id
    self.color = color or 2829617
    self.cache = Cache()
    self.proxy = COFFIN.proxy
    self.weather = API.weather
    self.captcha = COFFIN.captcha
    self.workers = Workers(COFFIN.workers, self.captcha)
    self.embed = ScriptedEmbed()
    self.shard_status = ShardStatus()
    self.started_at = datetime.now()
    self.shard_connected = {}
    self.toggled = False
    self.afk = {}
    self.reminder_tasks = defaultdict(dict)
    self.giveaways = {}
    self.prefixes = {}
    self.bots = {}
    self.blacktea_matches = {}
    self.blacktea_messages = {}
    self.blackjack_matches = []
    self.locks = defaultdict(asyncio.Lock)
    self.notified = defaultdict(bool)
    self.invite_regex = r"(https?://)?(www.|canary.|ptb.)?(discord.gg|discordapp.com/invite|discord.com/invite)[\/\\]?[a-zA-Z0-9]+/?"

  async def close(self):
    if self.browser:
      await self.browser.close()

    if getattr(self, "session"):
      await self.session.close()

    screenshots_path = Path("./screenshots")
    if screenshots_path.exists():
      for s in screenshots_path.iterdir():
        if s.is_file():
          os.remove(s)

    return await super().close()

  def run(self):
    return super().run(COFFIN.token, log_handler=None, reconnect=True)

  async def setup_hook(self: "Coffin"):
    self.session = ClientSession()
    self.db = await database.connect(self.dbname)
    self.add_check(self.check_command)

    blacklisted, afk = await asyncio.gather(
      self.db.fetch("SELECT target_id FROM blacklist"),
      self.db.fetch("SELECT * FROM afk")
    )
    self.blacklisted = list(map(lambda r: r["target_id"], blacklisted))
    self.tree.interaction_check = self.check_blacklisted

    for a in afk:
      model = Afk(**a)
      self.afk[str(model)] = model

    await self.load_extension("jishaku")
    tasks = [
      f"{'.'.join(cog.parts[:-1])}.{cog.stem}"
      for cog in Path("features").glob("**/*.py")
      if not (self.isinstance and cog.stem == "web")
    ]
    await asyncio.gather(*[self.load_extension(cog) for cog in tasks])

    for view in [VoiceMasterView(), TicketClose(), TicketView(), Giveaway()]:
      self.add_view(view)

  def humanize_date(self, date: datetime) -> str:
    """
    Humanize a datetime (ex: 2 days ago)
    """
    dated = (precisedelta(date, format='%0.0f').replace('and', ',')).split(', ')[0]
    return f"{dated} ago" if date.timestamp() < datetime.now().timestamp() else f"in {dated}"

  async def bump_cycle(self, guild_id: int):
    if result := await self.db.fetchrow(
      "SELECT * FROM bumpreminder WHERE guild_id = $1", guild_id
    ):
      time = (result.bump_next - utcnow()).total_seconds()
      await asyncio.sleep(time)

      if guild := self.get_guild(guild_id):
        member = guild.get_member(result.bumper_id) or guild.owner
        code = await self.embed.convert(member, result.remind)
        code.pop("delete_after", None)

        if channel := guild.get_channel(result.channel_id):
          await channel.send(**code)

  def replace_hex_chars(self, text: str):
    def hex_to_char(match):
      hex_value = match.group(0)
      return bytes.fromhex(hex_value[2:]).decode("utf-8")

    return re.sub(r"\\x[0-9a-fA-F]{2}", hex_to_char, text)

  def get_proxy(self) -> Proxy:
    args = self.flatten([p.split(":") for p in self.proxy[7:].split("@")])

    values = ["username", "password", "host", "port"]
    return Proxy(**dict(zip(values, args)))

  async def screenshot(self: "Coffin", url: str, wait: int) -> File:
    urlhash = md5(url.encode()).hexdigest()
    path = f"./screenshots/{urlhash}.{wait}.png"

    async with self.locks[path]:
      if os.path.exists(path):
        return File(path)

      if not re.match(r"^https?://", url):
        url = f"https://{url}"

      viewport = {"width": 1980, "height": 1080}
      proxy = self.get_proxy()

      if not self.browser:
        self.browser = await launch(
          headless=True,
          args=[
            "--no-sandbox", 
            f"--proxy-server={proxy.host}:{proxy.port}"
          ],
          defaultViewport=viewport,
        )

      page = await self.browser.newPage()
      keywords = re.compile(r"\b(?:pussy|tits|porn|cock|dick)\b", re.IGNORECASE)
      try:
        await page.authenticate(
          {"username": proxy.username, "password": proxy.password}
        )
        r = await page.goto(url, load=True, timeout=10000)
      except Exception:
        await page.close()
        raise BadArgument("Unable to screenshot page")

      if not r:
        await page.close()
        raise BadArgument("This page returned no response")

      if content_type := r.headers.get("content-type"):
        if not any(
          (i in content_type for i in ("text/html", "application/json"))
        ):
          await page.close()
          raise BadArgument("This kind of page cannot be screenshotted")

        content = await page.content()
        if keywords.search(content):
          await page.close()
          raise BadArgument(
            "This websites is most likely to contain explicit content"
          )

        await asyncio.sleep(wait)
        await page.screenshot(path=path)

        bad_filters = [
          "BUTTOCKS_EXPOSED",
          "FEMALE_BREAST_EXPOSED",
          "ANUS_EXPOSED",
          "FEMALE_GENITALIA_EXPOSED",
          "MALE_GENITALIA_EXPOSED",
        ]
        detections = await asyncio.to_thread(NudeDetector().detect, path)

        if any(
          [prediction["class"] in bad_filters for prediction in detections]
        ):
          os.remove(path)
          await page.close()
          raise BadArgument(
            "This websites is most likely to contain explicit content"
          )

        await page.close()
        return File(path)

  async def has_cooldown(self, interaction: Interaction) -> bool:
    ratelimit = ratelimiter(
      bucket=f"{interaction.channel.id}", key="globalratelimit", rate=3, per=3
    )

    if ratelimit:
      await interaction.response.defer(ephemeral=True)
    return bool(ratelimit)

  async def check_blacklisted(self, interaction: Interaction):
    objects = (interaction.user.id, getattr(interaction.guild, "id", 0))
    result = await self.db.fetchrow(
      f"SELECT * FROM blacklist WHERE target_id IN {objects}"
    )
    if result:
      message = (
        "You have been blacklisted from using coffin."
        if result.target_type == "user"
        else f"{interaction.guild} is blacklisted from using coffin's commands."
      )
      await interaction.alert(
        f"{message} Please join our [**support server**]({COFFIN.SUPPORT_URL}) and create a ticket for more information"
      )

    cooldown = await self.has_cooldown(interaction)
    return result is None and not cooldown

  async def leave_unauthorized(self):
    whitelisted = list(
      map(
        lambda r: r["guild_id"],
        await self.db.fetch("SELECT guild_id FROM authorize"),
      )
    )

    results = [g.id for g in self.guilds if g.id not in whitelisted]

    for guild_id in results:
      if g := self.get_guild(guild_id):
        await asyncio.sleep(0.1)
        await g.leave()

  @property
  def invite_url(self: "Coffin"):
    return oauth_url(self.user.id, permissions=Permissions(8))

  def parse_date(self: "Coffin", date: str) -> datetime:
    cal = pdt.Calendar()
    return cal.parseDT(date, datetime.now())[0]

  async def giveaway_task(
    self: "Coffin", message_id: int, channel_id: int, end_at: datetime
  ):
    now = datetime.now(tz=date_timezone.utc)
    if end_at > now:
      wait = (end_at - now).total_seconds()
      await asyncio.sleep(wait)

    del self.giveaways[message_id]
    gw = await self.db.fetchrow(
      "SELECT * FROM giveaway WHERE message_id = $1", message_id
    )
    if gw:
      try:
        winners = random.sample(gw.members, gw.winners)
        embed = (
          Embed(
            title=gw.reward,
            color=self.color,
            description=f"Ended: {format_dt(now, style='R')}",
          )
          .add_field(
            name=f"Winners ({gw.winners})",
            value=", ".join(list(map(lambda m: f"<@{m}>", winners))),
          )
          .set_footer(text="coffin.lol")
        )
      except ValueError:
        embed = Embed(
          title=gw.reward,
          color=self.color,
          description=f"Not enough participants in the giveaway",
        ).set_footer(text="coffin.lol")
      finally:
        await self.db.execute(
          "UPDATE giveaway SET ended = $1 WHERE message_id = $2",
          True,
          message_id,
        )
        with suppress(Exception):
          message = await self.get_channel(channel_id).fetch_message(message_id)
          await message.edit(embed=embed, view=None)
          await message.reply(f"{', '.join(list(map(lambda m: f'<@{m}>', winners)))} has won the prize for **{gw.reward}**")

  async def reminder_task(
    self: "Coffin",
    user_id: int,
    reminder: str,
    remind_at: datetime,
    invoked_at: datetime,
    task_number: int,
  ):
    remind_at = remind_at.replace(tzinfo=date_timezone.utc)
    invoked_at = invoked_at.replace(tzinfo=date_timezone.utc)

    async def send_reminder():
      del self.reminder_tasks[str(user_id)][str(task_number)]
      if user := self.get_user(user_id):
        embed = Embed(
          color=self.color, description=f"â° {reminder}"
        ).set_footer(
          text=f"You told me to remind you that {humanize.naturaltime(invoked_at)}"
        )
        with suppress(Exception):
          await user.send(embed=embed)
          await self.db.execute(
            "DELETE FROM reminders WHERE user_id = $1 AND remind_at = $2 AND invoked_at = $3",
            user_id,
            remind_at,
            invoked_at,
          )

    if remind_at.timestamp() < datetime.now().timestamp():
      return await send_reminder()

    wait_for = (remind_at - datetime.now(date_timezone.utc)).total_seconds()
    await asyncio.sleep(wait_for)
    return await send_reminder()

  @cached_property
  def files(self) -> List[str]:
    return [
      f"{root}/{f}"
      for root, _, file in os.walk("./")
      for f in file
      if f.endswith((".py", ".html", ".js", ".css"))
      and ".venv" not in root
    ]

  @cached_property
  def lines(self) -> int:
    return sum(len(open(f).readlines()) for f in self.files)

  def size_to_bytes(self: "Coffin", size: str):
    size_name = ["B", "KB", "MB", "GB", "TB"]
    return int(
      math.pow(1024, size_name.index(size.split(" ")[1]))
      * float(size.split(" ")[0])
    )
  
  async def urltobyte(self: "Coffin", url: str) -> BytesIO:
    return BytesIO(await self.session.get(url))

  def flatten(self: "Coffin", data: list) -> list:
    return [i for y in data for i in y]

  async def on_shard_connect(self: "Coffin", shard_id: int):
    if not self.isinstance:
      self.shard_connected[shard_id] = datetime.now()

  async def on_shard_disconnect(self: "Coffin", shard_id: int):
    if not self.isinstance:
      self.shard_connected[shard_id] = datetime.now()

  async def on_shard_ready(self: "Coffin", shard_id: int):
    if not self.isinstance:
      if not hasattr(self, "shard_channel"):
        self.shard_channel = self.get_channel(1290876480079003719)

      now = datetime.now(timezone("US/Eastern")).strftime("%B %d %Y %I:%M %p")
      ready_in = humanize.naturaldelta(
        datetime.now() - self.shard_connected[shard_id]
      )
      embed = Embed(
        color=self.shard_status.ok,
        description=f">>> [**UPTIME STATUS**] :: {now} EST :: Bot is back **online** on shard **{shard_id}** for {len(self.guilds):,} servers after **{ready_in}**.",
      )
      return await self.shard_channel.send(embed=embed)

  async def toggle_instances(self):
    if not self.toggled:
      instances = await self.db.fetch("SELECT * FROM instances")
      for instance in instances:
        b = Coffin(
          instance_owner_id=instance.owner_id,
          color=instance.color,
          instance=True,
          dbname=instance.dbname,
          status=getattr(Status, instance.status),
          node=self.node,
          activity=CustomActivity(name=instance.activity),
        )
        self.bots[instance.dbname] = {"owner_id": instance.owner_id, "bot": b}
        asyncio.ensure_future(b.start(instance.token))

      self.toggled = True

  async def manage_notified(self, after: Member):
    if not self.notified.get(after.guild.id):
      self.notified[after.guild.id] = {} 
    
    self.notified[after.guild.id][after.id] = True
    await asyncio.sleep(600)
    self.notified.get(after.guild.id, {}).pop(after.id, None)

  async def on_presence_update(self, before: Member, after: Member):
    async with self.locks[after.guild.id]:
      if not after.bot:
        if vanity_code := before.guild.vanity_url_code:
          if not str(before.status) == "offline" and not str(after.status) == "offline":
            if result := await self.db.fetchrow("SELECT * FROM vanity WHERE guild_id = $1", before.guild.id):
              if result.roles:
                if isinstance(before.activity, CustomActivity) or isinstance(after.activity, CustomActivity):
                  if f"/{vanity_code}" not in getattr(before.activity, "name", "") and f"/{vanity_code}" in getattr(after.activity, "name", ""):
                    #has the vanity in status 

                    roles = after.roles 
                    roles.extend(
                      [
                        after.guild.get_role(r) 
                        for r in result.roles 
                        if after.guild.get_role(r)
                        and after.guild.get_role(r).is_assignable()
                        and after.guild.get_role(r) not in roles
                      ]
                    )

                    if roles != after.roles:
                      await after.edit(
                        roles=roles,
                        reason="Member has the server's vanity in status"
                      )

                    if not self.notified.get(after.guild.id, {}).get(after.id): 
                      if channel := before.guild.get_channel(result.channel_id):
                        asyncio.ensure_future(self.manage_notified(after))
                        script = await self.embed.convert(after, result.message)
                        script.pop('delete_after', None) 
                        return await channel.send(**script)
                          
                  elif f"/{vanity_code}" in getattr(before.activity, "name", "") and f"/{vanity_code}" not in getattr(after.activity, "name", ""):
                    #removed the vanity from the status

                    roles = after.roles 
                    for role in [r for r in after.roles if r.is_assignable() and r.id in result.roles]:
                      roles.remove(role)
                    
                    if roles != after.roles:
                      return await after.edit(
                        roles=roles,
                        reason="Member isn't repping the server anymore"
                      )

  async def on_ready(self: "Coffin"):
    if not self.isinstance:
      await self.build_cache()
      # asyncio.ensure_future(self.leave_unauthorized())
      youtube_notifications.start(self)
      twitch_notifications.start(self)
      fnshop_notifications.start(self)
      await self.toggle_instances()

    self.logger.info(f"Logged in as {self.user.name} with {len(set(self.walk_commands()))} commands and {len(self.cogs)} cogs loaded!")

  def build_methods(self):
    guild = self.get_guild(1183940972137173162)

    User.is_developer = Member.is_developer = property(
      fget=lambda m: guild.get_role(1241559595173019678)
      in getattr(guild.get_member(m.id), "roles", []),
    )
    User.is_manager = Member.is_manager = property(
      fget=lambda m: guild.get_role(1290885018641502281)
      in getattr(guild.get_member(m.id), "roles", [])
    )
    User.is_staff = Member.is_staff = property(
      fget=lambda m: guild.get_role(1290884914379624500)
      in getattr(guild.get_member(m.id), "roles", [])
    )
    User.web_status = property(
      fget=lambda m: (
        m.mutual_guilds[0].get_member(m.id).web_status
        if m.mutual_guilds
        else Status.offline
      )
    )
    User.mobile_status = property(
      fget=lambda m: (
        m.mutual_guilds[0].get_member(m.id).mobile_status
        if m.mutual_guilds
        else Status.offline
      )
    )
    User.desktop_status = property(
      fget=lambda m: (
        m.mutual_guilds[0].get_member(m.id).desktop_status
        if m.mutual_guilds
        else Status.offline
      )
    )
    User.activity = property(
      fget=lambda m: (
        m.mutual_guilds[0].get_member(m.id).activity
        if m.mutual_guilds
        else None
      )
    )

  async def fetch_application(self, user: Union[Member, User]) -> ApplicationInfo:
    if cache := self.cache.get(f"appinfo-{user.id}"):
      return cache

    x = await self.session.get(
      f"https://discord.com/api/v10/oauth2/applications/{user.id}/rpc",
      headers={"Authorization": self.http.token},
    )

    flags = {
      1 << 12: "Presence",
      1 << 13: "Presence",
      1 << 14: "Guild Members",
      1 << 15: "Guild Members",
      1 << 18: "Message Content",
      1 << 19: "Message Content",
    }

    legal = ApplicationLegal(
      terms=x.terms_of_service_url or "https://none.none",
      privacy=x.privacy_policy_url or "https://none.none",
    ) if x.terms_of_service_url else None

    info = ApplicationInfo(
      bio=x.description,
      flags=[name for bit, name in flags.items() if x["flags"] & bit],
      tags=x.tags,
      legal=legal,
    )
    await self.cache.add(f"appinfo-{user.id}", info, 3600)
    return info

  async def build_cache(self):
    self.build_methods()
    reminders, giveaways, bumpreminder_guilds = await asyncio.gather(
      self.db.fetch("SELECT * FROM reminders ORDER BY remind_at ASC"),
      self.db.fetch("SELECT * FROM giveaway WHERE NOT ended"),
      self.db.fetch("SELECT guild_id FROM bumpreminder WHERE bump_next IS NOT NULL")
    )
    sorted_reminders = defaultdict(list)

    for result in bumpreminder_guilds:
      asyncio.ensure_future(self.bump_cycle(result["guild_id"]))

    for reminder in reminders:
      sorted_reminders[reminder.user_id].append(reminder)

    for giveaway in giveaways:
      self.giveaways[giveaway.message_id] = asyncio.ensure_future(
        self.giveaway_task(
          **dict(giveaway)
        )
      )

    for k, v in sorted_reminders.items():
      for idx, reminder in enumerate(v, start=1):
        await asyncio.sleep(0.1)

        if not self.reminder_tasks.get(k):
          self.reminder_tasks[k] = {}

        r = dict(reminder)
        r["task_number"] = idx
        self.reminder_tasks[k][str(idx)] = asyncio.ensure_future(
          self.reminder_task(**r)
        )

    sorted_reminders.clear()

  async def process_commands(self: "Coffin", message: Message):
    if message.guild:
      if message.content.startswith(tuple(await bot_prefix(self, message))):
        if not ratelimiter(
          bucket=f"{message.channel.id}", key="globalratelimit", rate=3, per=3
        ):
          with suppress(NotFound):
            return await super().process_commands(message)

  async def on_guild_join(self, guild: Guild):
    if await self.db.fetchrow(
      "SELECT * FROM blacklist WHERE target_id = $1", guild.id
    ):
      return await guild.leave()

    channel = guild.system_channel or (
      next(
        (
          c
          for c in guild.text_channels
          if c.permissions_for(guild.me).send_messages
        ),
        None,
      )
    )

    if self.isinstance:
      if not await self.db.fetchrow(
        "SELECT * FROM authorize WHERE guild_id = $1", guild.id
      ):
        if channel:
          await channel.send(
            f"<a:sw_wavecatboy:1279915075414786191> this server is not authorized join [here](<{COFFIN.SUPPORT_URL}>) to get your server authorized"
          )

        return await guild.leave()
                
  async def on_message_edit(self: "Coffin", before: Message, after: Message):
    if before.content != after.content:
      await self.on_message(after)

  async def get_context(self: "Coffin", message: Message, *, cls=Context) -> Context:
    return await super().get_context(message, cls=cls)

  async def on_command(self: "Coffin", ctx: Context):
    await self.db.execute(
      """
      INSERT INTO topcmds 
      VALUES ($1,$2)
      ON CONFLICT (name)
      DO UPDATE SET count = topcmds.count + $2 
      """,
      ctx.command.qualified_name,
      1,
    )

    if ctx.guild:
      self.logger.info(
        f"{ctx.author} ({ctx.author.id}) executed {ctx.command} in {ctx.guild} ({ctx.guild.id}). (msg: {ctx.message.content})"
      )

  def naive_grouper(self: "Coffin", data: list, group_by: int) -> list:
    if len(data) <= group_by:
      return [data]

    groups = len(data) // group_by
    return [list(data[i * group_by : (i + 1) * group_by]) for i in range(groups)]

  async def on_command_error(
    self: "Coffin", ctx: Context, exception: CommandError
  ) -> Optional[Message]:
    exception = getattr(exception, "original", exception)
    if type(exception) in (NotOwner, CommandOnCooldown, UserInputError):
      return

    if isinstance(exception, CommandInvokeError):
      exception = exception.original

    if isinstance(
      exception,
      (
        MissingRequiredArgument,
        MissingRequiredFlag,
        BadLiteralArgument,
        MissingRequiredAttachment,
      ),
    ):
      return await ctx.send_help(ctx.command)

    elif isinstance(exception, CommandNotFound):
      alias = ctx.message.content[len(ctx.clean_prefix) :].split(" ")[0]
      cmd = await self.db.fetchval(
        "SELECT command FROM aliases WHERE alias = $1 AND guild_id = $2",
        alias,
        ctx.guild.id,
      )

      if cmd:
        ctx.message.content = ctx.message.content.replace(alias, cmd, 1)
        return await self.process_commands(ctx.message)
      return

    elif isinstance(exception, BadArgument):
      return await ctx.alert(exception.args[0])

    elif isinstance(exception, CheckFailure):
      if isinstance(exception, MissingPermissions):
        return await ctx.alert(
          f"You are missing permissions: {', '.join(map(lambda p: f'`{p}`', exception.missing_permissions))}"
        )
      return

    elif isinstance(exception, Error):
      return await ctx.neutral(exception.message)

    elif isinstance(exception, ClientConnectorError):
      return await ctx.alert("The API has timed out!")

    elif isinstance(exception, ClientResponseError):
      return await ctx.send(
        file=File(
          BytesIO(
            await self.session.get(f"https://http.cat/{exception.status}")
          ),
          filename="status.png",
      )
      )

    return await ctx.alert(f"{exception}")

  async def check_command(self, ctx: Context):
    if not ctx.guild:
      return True

    if r := await self.db.fetchrow(
      """
      SELECT * FROM disabledcmds 
      WHERE guild_id = $1 
      AND command_name = $2
      """,
      ctx.guild.id,
      ctx.command.qualified_name,
    ):
      await ctx.neutral(
        f"**{ctx.command.qualified_name}** is disabled in this server"
      )

    return not r

  def check_message(self: "Coffin", message: Message) -> bool:
    return (
      self.is_ready() and
      not message.author.bot and
      message.guild is not None and
      message.author.id not in self.blacklisted
    )

  async def on_channel_delete(self, channel):
    if not self.isinstance:
      await self.db.execute(
        "DELETE FROM opened_tickets WHERE channel_id = $1", channel.id
      )

  async def on_message(self: "Coffin", message: Message) -> None:
    if self.check_message(message):
      if message.content == self.user.mention:
        prefix = await self.get_prefix(message)
        return await message.channel.send(f"guild prefix: `{prefix[-1]}`")

      await self.process_commands(message)

async def bot_prefix(bot: Coffin, message: Message):
  if not (prefix := bot.prefixes.get(message.guild.id)):
    prefix: str = (
      await bot.db.fetchval(
        "SELECT prefix FROM prefix WHERE guild_id = $1", message.guild.id
      )
      or ","
    )
    bot.prefixes.setdefault(message.guild.id, prefix)

  return when_mentioned_or(prefix)(bot, message)

@tasks.loop(minutes=3)
async def twitch_notifications(bot: Coffin):
  results = await bot.db.fetch(
    """
    SELECT
      streamer, 
      ARRAY_AGG(ARRAY[channel_id::TEXT, stream_id, content]) as twitch_pairs
    FROM notifications.twitch
    GROUP BY streamer
    """
  )
  
  headers = {
    "client-id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
    "client-session-id": "bc9cdea175eb84bf",
    "client-version": "cf0f573f-6d51-4d85-9c59-0a9ce7301b38", 
    "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"
  }
  for result in results: 
    payload = [
      {
        "operationName":"MwebChannelHomePage_Query",
        "variables":{
          "login": result.streamer
        },
        "extensions":{
          "persistedQuery":{
            "version":1,
            "sha256Hash":"9795cac5a29b76b1800d5472f92a5a9c68d192820f9a52b7fdaddd2438584ce6"
          }
        }
      },
      {
        "operationName":"HomeTrackQuery",
        "variables":{
          "channelLogin":result.streamer
        },
        "extensions":{
          "persistedQuery":{
              "version":1,
              "sha256Hash":"129cbf14117ce8e95f01bd2043154089058146664df866d0314e84355ffb4e05"
          }
        }
      },
      {
        "operationName":"ChannelLayout",
        "variables":{
          "channelLogin":result.streamer,
          "includeIsDJ":True
        },
        "extensions":{
          "persistedQuery":{
            "version":1,
            "sha256Hash":"243697c79ec36b21d8b00ba962120cfecab171af15882ddcefd39266f35d3e0a"
          }
        }
      }
    ]
    res = await bot.session.post(
      "https://gql.twitch.tv/gql",
      headers=headers,
      json=payload
    )
    ch = res[0].data.channel
    username = ch.login
    display_name = ch.displayName
    if ch.stream:
      kwargs = {
        'width': "1980",
        'height': "1080"
      }
      preview_image = ch.stream.previewImageURL.format(**kwargs)
      game = ch.stream.game.displayName
      title = ch.stream.broadcaster.broadcastSettings.title
      stream_id = ch.stream.id
      for pair in result.twitch_pairs:
        last_id = pair[1] or ""
        if last_id != stream_id:
          await bot.db.execute(
            """
            UPDATE notifications.twitch
            SET stream_id = $1
            WHERE channel_id = $2
            AND streamer = $3 
            """,
            stream_id, int(pair[0]),
            result.streamer
          ) 
          
          if channel := bot.get_channel(int(pair[0])):
            embed = (
              Embed(
                title=title,
                color=0x6441a4,
                url=f"https://twitch.tv/{username}",
                timestamp=utcnow()
              )
              .set_author(name=f"{display_name} | {game}")
              .set_image(url=preview_image)
              .set_footer(text="Twitch")
            )
            
            content = pair[2].replace('{streamer}', username)

            with suppress(Exception):
              await channel.send(
                content=content,
                embed=embed,
                allowed_mentions=AllowedMentions.all()
              )
            
            await asyncio.sleep(0.5)

@tasks.loop(minutes=3)
async def youtube_notifications(bot: Coffin):
  results = await bot.db.fetch(
    """
    SELECT 
      youtuber, 
      ARRAY_AGG(ARRAY[channel_id::TEXT, last_stream, content]) as youtuber_pairs
    FROM notifications.youtube
    GROUP BY youtuber
    """
  )
  for result in results:
    html = await bot.session.get(
      f"https://youtube.com/@{result.youtuber}/streams",
      headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
      },
    )
    soup = BeautifulSoup(html, "html.parser")
    s = re.search(r"var ytInitialData = (.*)", soup.prettify()).group(1)
    payload = json.loads(
      json.loads(json.dumps(bot.replace_hex_chars(s)[1:-2])).replace('\\\\"', "'")
    )
    stream = payload["contents"]["singleColumnBrowseResultsRenderer"]["tabs"][3][
      "tabRenderer"
    ]["content"]["richGridRenderer"]["contents"][0]["richItemRenderer"]["content"][
      "compactVideoRenderer"
    ]
    status = stream["thumbnailOverlays"][0]["thumbnailOverlayTimeStatusRenderer"][
      "text"
    ]["runs"][0]["text"]
    url = f"https://youtube.com/watch?v={stream['videoId']}"
    thumbnail = stream["thumbnail"]["thumbnails"][-1]["url"]
    title = stream["title"]["runs"][0]["text"]
    name = soup.find("meta", property="og:title")["content"]
    image = soup.find("meta", property="og:image")["content"]
    youtuber_url = soup.find("meta", property="og:url")["content"]
    embed = (
      Embed(
        color=0xFF0000, 
        title=title, 
        url=url, 
        timestamp=utcnow()
      )
      .set_author(name=name, icon_url=image, url=youtuber_url)
      .set_image(url=thumbnail)
      .set_footer(text="Youtube")
    ) 
    if status == "LIVE":
      for pair in result.youtuber_pairs:
        if channel := bot.get_channel(int(pair[0])):
          last_stream = pair[1] or ""
          if last_stream != stream["videoId"]:
            await bot.db.execute(
              """
              UPDATE notifications.youtube 
              SET last_stream = $1 
              WHERE youtuber = $2
              AND channel_id = $3
              """,
              stream["videoId"],
              result.youtuber,
              int(pair[0])
            )

            content = pair[2].replace('{youtuber}', name)

            with suppress(Exception):
              await channel.send(
                content=content, 
                embed=embed,
                allowed_mentions=AllowedMentions.all()
                )
                
            await asyncio.sleep(0.5)
            
@tasks.loop(minutes=3)
async def fnshop_notifications(bot: Coffin):
  r = await bot.db.fetch(
    """
    SELECT
      guild_id, 
      ARRAY_AGG(ARRAY[channel_id::TEXT, role_id::TEXT, hash_id]) as guild_pairs,
      ARRAY_AGG(reactions) as reactions
    FROM notifications.fortnite
    GROUP BY guild_id
    """
  )
  data = await bot.session.get(
    f"https://bot.fnbr.co/shop-image/fnbr-shop-{utcnow().strftime('%-d-%-m-%Y')}.png"
  )
  new_hash = sha256(data).hexdigest()
  for result in r:
    for pair, reactions in zip(result.guild_pairs, result.reactions):
      if new_hash != pair[2]:
        await bot.db.execute(
          """
          INSERT INTO notifications.fortnite (guild_id, hash_id)
          VALUES ($1, $2) ON CONFLICT (guild_id)
          DO UPDATE SET hash_id = $2
          """,
          result.guild_id, new_hash
        )

        if (channel := bot.get_channel(int(pair[0]))):
          m = await channel.send(
              content=f"{f'<@&{pair[1]}>' if pair[1] else ''} Fortnite Shop for **{utcnow().strftime('%A, %b %d, %Y')}**",
              file=File(BytesIO(data), filename="shop.png"),
              allowed_mentions=AllowedMentions.all()
          )
          for r in reactions:
            await asyncio.sleep(0.001)
            await m.add_reaction(r)

          await asyncio.sleep(0.5)