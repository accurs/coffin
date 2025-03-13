import discord
import asyncio
import datetime
import json
import re
import sys
import os
import aiofiles

from zipfile import ZipFile
from io import BytesIO
from discord.utils import format_dt, utcnow
from jishaku.codeblocks import codeblock_converter

from discord import (
  File,
  HTTPException,
  CustomActivity,
  Embed,
  Guild,
  Invite,
  Member,
  Message,
  Permissions,
  Status,
  Thread,
  User,
  Message,
  TextChannel
)
from discord.ext.commands import (
  Cog,
  CommandError,
  CommandInvokeError,
  CurrentGuild,
  ExtensionAlreadyLoaded,
  ExtensionFailed,
  ExtensionNotFound,
  ExtensionNotLoaded,
  command,
  group
)
from typing import (
  Literal,
  Optional,
  List,
  Union
)
from structure import (
  Coffin,
  Context,
  getLogger
)

logger = getLogger(__name__)

class Developer(Cog, command_attrs=dict(hidden=True)):
  def __init__(self, bot: Coffin):
    self.bot = bot
    self.channel_id = 1290876630318714990
    self.commandchannel_id = 1326216297977086034

  def get_command_hierarchy(self, context: Context) -> str:
    parts = list()
    CAT = "┌── "
    CMD = "|    ├──  "
    SUB = "|    |   ├── "

    for cog in sorted(
      [
        context.bot.get_cog(cog)
        for cog in context.bot.cogs
        if context.bot.get_cog(cog).get_commands()
        and context.bot.get_cog(cog).qualified_name
        not in ("Jishaku", "Developer")
      ],
      key=lambda c: c.qualified_name[:2],
    ):
      parts.append(f"{CAT}{cog.qualified_name.replace('_', ' ')}")
      for cmd in cog.get_commands():
        parts.append(
          f"{CMD}{cmd.qualified_name}"
          + (f"[{'|'.join(cmd.aliases)}]" if cmd.aliases else "")
          + f": {cmd.description}"
        )
        if hasattr(cmd, "commands"):
          for c in cmd.walk_commands():
            parts.append(
              f"{SUB}{c.qualified_name}"
              + (f"[{'|'.join(c.aliases)}]" if c.aliases else "")
              + f": {c.description}"
            )

    return "\n".join(parts)

  def is_owner(self, ctx: Context) -> bool:
    if guild := self.bot.get_guild(1183940972137173162):
      if member := guild.get_member(ctx.author.id):
        return member.get_role(1241559595173019678)

    return False

  async def cog_check(self: "Developer", ctx: Context) -> bool:
    if await self.bot.is_owner(ctx.author) or self.is_owner(ctx):
      return True

  @Cog.listener()
  async def on_member_join(self, member: Member):
    reason = await self.bot.db.fetchval(
      "SELECT reason FROM globalban WHERE user_id = $1", member.id
    )
    if reason:
      if member.guild.me.guild_permissions.ban_members:
        await member.ban(reason=reason)

  @Cog.listener("on_message")
  async def wave(self, message: discord.Message):
    if not self.bot.isinstance:
      if (
        message.is_system()
        and message.guild
        and message.guild.id == 1183940972137173162
        and message.type == discord.MessageType.new_member
      ):
        logger.info("meow  %s", message.guild.name)

        sticker = self.bot.get_sticker(1270909925522018368)

        if sticker is None:
          logger.info("fuck.")
          return

        logger.info("R: %s", sticker.id)
        return await message.reply(stickers=[sticker])

      if message.guild is None:
        logger.info("dms.")

  @Cog.listener()
  async def on_guild_join(self, guild: Guild):
    if self.bot.is_ready() and not self.bot.isinstance:
      await self.bot.get_channel(self.channel_id).send(
        f"Joined {guild.name} (`{guild.id}`) with {guild.member_count} members owned by {guild.owner} (`{guild.owner.id}`)"
      )

  @Cog.listener()
  async def on_guild_remove(self, guild: Guild):
    if self.bot.is_ready() and not self.bot.isinstance:
      await self.bot.get_channel(self.channel_id).send(
        f"Left {guild.name} (`{guild.id}`) with {guild.member_count} members owned by {guild.owner} (`{guild.owner.id}`)"
      )

  @Cog.listener()
  async def on_message(self, message: Message):
    if getattr(message.guild, "id", 0) == 1183940972137173162:
      if message.type.__str__().startswith("MessageType.premium_guild"):
        await self.bot.db.execute(
          """
          INSERT INTO donator (user_id, reason) VALUES ($1,$2)
          ON CONFLICT (user_id) DO NOTHING
          """,
          message.author.id,
          "boosted",
        )

  @Cog.listener()
  async def on_member_remove(self, member: Member):
    if getattr(member.guild, "id", 0) == 1183940972137173162:
      await self.bot.db.execute(
        "DELETE FROM donator WHERE user_id = $1 AND reason = $2",
        member.id,
        "boosted",
      )

  @Cog.listener()
  async def on_member_update(self, before: Member, after: Member):
    if getattr(before.guild, "id", 0) == 1183940972137173162:
      if before.premium_since and not after.premium_since:
        await self.bot.db.execute(
          "DELETE FROM donator WHERE user_id = $1 AND reason = $2",
          after.id,
          "boosted",
        )

  @group(invoke_without_command=True)
  async def sudo(
    self,
    ctx: Context,
    channel: Optional[TextChannel],
    target: Member,
    *,
    command: str,
  ) -> None:
    """
    Run a command as another user.
    """
    ctx.message.channel = channel or ctx.channel
    ctx.message.author = target or ctx.guild.owner or ctx.author
    ctx.message.content = f"{ctx.prefix or ctx.settings.prefixes[0]}{command}"

    new_ctx = await self.bot.get_context(ctx.message, cls=type(ctx))
    return await self.bot.invoke(new_ctx)

  @sudo.command(name="commands")
  async def sudo_commands(self, ctx: Context):
    """
    Shows the command hierarchy of the bot
    """
    hierarchy = self.get_command_hierarchy(ctx)

    if hierarchy:
      path = "commands.txt"
      async with aiofiles.open(path, "w", encoding="utf-8") as file:
        await file.write(hierarchy)

      async with aiofiles.open(path, "rb") as file:
        await ctx.send(file=discord.File(BytesIO(await file.read()), path))

      os.remove(path)
    else:
      return

  @sudo.command(name="send", aliases=["dm"])
  async def sudo_send(
    self,
    ctx: Context,
    target: Optional[Member | User],
    *,
    content: str,
  ) -> Optional[Message]:
    """
    Send a message to a user.
    """
    try:
      await target.send(content, delete_after=15)
    except HTTPException as exc:
      return await ctx.alert("Failed to send the message!", exc.text)

    return await ctx.message.add_reaction("✅")

  @sudo.command(name="restart", aliases=["re", "reboot", "res", "reset"])
  async def sudo_restart(self: "Developer", ctx: Context):
    """
    Restart the bot
    """
    await ctx.message.add_reaction("✅")
    python = sys.executable
    os.execv(python, [python] + sys.argv)

  @sudo.command(name="x")
  async def sudo_x(
    self,
    ctx: Context,
    *,
    guild: Guild,
  ) -> None:
    async with ctx.typing():
      for channel in guild.text_channels:
        result: List[str] = []
        async for message in channel.history(limit=500, oldest_first=True):
          result.append(
            f"[{message.created_at:%d/%m/%Y - %H:%M}] {message.author} ({message.author.id}): {message.system_content}"
          )

        if not result:
          continue

        await ctx.message.add_reaction("▶️")
        await ctx.send(
          file=File(
            BytesIO("\n".join(result).encode()),
            filename=f"{channel.name}.txt",
          ),
        )

    return await ctx.message.add_reaction("✅")

  @group(invoke_without_command=True)
  async def data(self, ctx: Context):
    """
    Manage the data overall
    """
    return await ctx.send_help(ctx.command)

  @data.command(name="clear", aliases=["remove", "delete", "del"])
  async def data_delete(self, ctx: Context, *, target: Union[User, Guild]):
    """
    Delete data from a certain guild or user
    """
    async def yes(interaction: discord.Interaction):
      column = "user_id" if isinstance(target, User) else "guild_id"
      tables = await interaction.client.db.fetch(
        """
        SELECT table_schema, table_name
        FROM information_schema.columns
        WHERE column_name = $1
        """,
        column,
      )

      for table in tables:
        await interaction.client.db.execute(
          f"""
          DELETE FROM {'.'.join(dict(table).values())}
          WHERE {column} = $1 
          """,
          target.id,
        )

      embed = interaction.message.embeds[0]
      embed.description = (
        f"Removed all data from **{target.name}** (`{target.id}`)"
      )
      return await interaction.response.edit_message(embed=embed, view=None)

    return await ctx.confirmation(
      f"Are you sure you want to delete all data matching with **{target.name}** (`{target.id}`)? This action is permanent",
      yes,
    )

  @data.command(name="pull")
  async def data_pull(self, ctx: Context, *, target: Union[User, Guild]):
    """
    Pull all data from a member or guild in a zip file
    """
    column = "user_id" if isinstance(target, User) else "guild_id"
    tables = await self.bot.db.fetch(
      """
      SELECT table_schema, table_name
      FROM information_schema.columns
      WHERE column_name = $1
      """,
      column,
    )

    buffer = BytesIO()
    await ctx.send(
      f"Pulling data from {'guild' if column == 'guild_id' else 'user'} **{target.name}**"
    )
    async with ctx.typing():
      with ZipFile(buffer, "w") as my_zip:
        for table in tables:
          if results := await self.bot.db.fetch(
            f"SELECT * FROM {'.'.join(dict(table).values())} WHERE {column} = $1",
            target.id,
          ):
            my_zip.writestr(
              f"{'.'.join(dict(table).values())}.json",
              data=json.dumps(
                [
                  {
                    k: (
                      v
                      if not isinstance(v, datetime.datetime)
                      else v.isoformat()
                    )
                  }
                  for result in results
                  for k, v in dict(result).items()
                ]
              ),
            )

      buffer.seek(0)
      return await ctx.send(
        f"The data for **{target.name}** (`{target.id}`) is here:",
        file=discord.File(buffer, filename=f"{target.name}.zip"),
      )

  @command()
  async def closethread(self, ctx: Context):
    """
    Close a thread
    """
    if ctx.guild.id == 1183940972137173162:
      if isinstance(ctx.channel, Thread):
        return await ctx.channel.delete()

  @command()
  async def sync(self, ctx: Context):
    """
    syncs the bot's slash & user app commands
    """
    await ctx.message.add_reaction("⌛")
    await self.bot.tree.sync()
    await ctx.message.clear_reactions()
    return await ctx.message.add_reaction("✅")

  @command()
  async def load(
    self: "Developer",
    ctx: Context,
    feature: str
  ) -> Message:
    """
    Load an existing feature.
    """
    try:
      await self.bot.load_extension(feature)
    except (ExtensionFailed, ExtensionNotFound, ExtensionAlreadyLoaded) as e:
      return await ctx.alert(
        f"> Failed to load `{feature}`: {type(e).__name__}\n```py\n{e}```"
      )

    return await ctx.message.add_reaction("✅")

  @command()
  async def mutuals(self, ctx: Context, *, user: User):
    """
    Get a person's mutual guilds with the bot
    """
    if not user.mutual_guilds:
      return await ctx.alert(
        f"This user does not have any mutual guilds with **{self.bot.user.name}**"
      )

    return await ctx.paginate(
      [f"**{guild}** (`{guild.id}`)" for guild in user.mutual_guilds],
      Embed(title=f">>> Mutual guild(s)"),
    )

  @command()
  async def authorized(self, ctx: Context, *, user: Optional[User] = None):
    """
    Check all authorized servers
    """
    results = (
      await self.bot.db.fetch(
        "SELECT * FROM authorize WHERE owner_id = $1", user.id
      )
      if user
      else await self.bot.db.fetch("SELECT * FROM authorize")
    )

    if not results:
      return await ctx.alert(
        f"There are **no** authorized servers {f'for **{user}**' if user else ''}"
      )

    return await ctx.paginate(
      [
        f"{self.bot.get_guild(result.guild_id) or 'Unknown server'} (`{result.guild_id}`) {f'authorized for <@{result.owner_id}>' if not user else ''}"
        for result in results
      ],
      Embed(title=f"Authorized servers ({len(results)})"),
    )

  @command()
  async def auth(self, ctx: Context, guild_id: int, *, user: User):
    """
    Authorize a server
    """
    await self.bot.db.execute(
      """
      INSERT INTO authorize VALUES ($1,$2)
      ON CONFLICT (guild_id) DO NOTHING
      """,
      guild_id,
      user.id,
    )

    return await ctx.confirm(f"Guild `{guild_id}` was authorized for **{user}**")

  @command()
  async def unauth(self, ctx: Context, guild_id: int):
    """
    Unauthorize a server
    """
    await self.bot.db.execute("DELETE FROM authorize WHERE guild_id = $1", guild_id)

    if guild := self.bot.get_guild(guild_id):
      await guild.leave()
      return await ctx.confirm(f"Unauthorized **{guild}** (`{guild_id}`)")

    return await ctx.confirm(f"Unauthorized `{guild_id}`")

  @command(aliases=["gbanned"])
  async def globalbanned(self: "Developer", ctx: Context):
    """
    Get a list of globalbanned users
    """
    results = await self.bot.db.fetch("SELECT * FROM globalban")
    if not results:
      return await ctx.alert("There are **no** globalbanned users")

    return await ctx.paginate(
      [
        f"{self.bot.get_user(result.user_id) or f'<@{result.user_id}>'} (`{result.user_id}`) - {result.reason}"
        for result in results
      ],
      Embed(title=f">>> Global Banned users ({len(results)})"),
    )

  @command(aliases=["gban", "gb", "global", "banglobally"])
  async def globalban(
    self,
    ctx: Context,
    user: User,
    *,
    reason: str = "Globally Banned User",
  ):
    """
    Ban an user globally
    """
    if user.id in self.bot.owner_ids:
      return await ctx.alert(">>> Do not global ban a bot owner, retard")

    check = await self.bot.db.fetchrow("SELECT * FROM globalban WHERE user_id = $1", user.id)
    if check:
      await self.bot.db.execute(
        "DELETE FROM globalban WHERE user_id = $1", user.id
      )
      return await ctx.confirm(
        f">>> {user.mention} was succesfully globally unbanned"
      )

    mutual_guilds = len(user.mutual_guilds)
    tasks = [
      g.ban(user, reason=reason)
      for g in user.mutual_guilds
      if g.me.guild_permissions.ban_members
      and g.me.top_role > g.get_member(user.id).top_role
      and g.owner_id != user.id
    ]
    await asyncio.gather(*tasks)
    await self.bot.db.execute(
      "INSERT INTO globalban VALUES ($1,$2)", user.id, reason
    )
    return await ctx.confirm(
      f">>> {user.mention} was succesfully globally banned in {len(tasks)}/{mutual_guilds} servers"
    )

  @command()
  async def pull(self: "Developer", ctx: Context):
    """
    Pull the latest commit of the repository
    """
    return await ctx.invoke(
      self.bot.get_command("shell"), argument=codeblock_converter("git pull")
    )

  @command(name="debug", aliases=["dbg"])
  async def cmd_debug(self: "Developer", ctx: Context, *, command_string: str):
    """
    Debug a bot command
    """
    return await ctx.invoke(
      self.bot.get_command("jsk dbg"), command_string=command_string
  )

  @command(aliases=["sh", "terminal", "bash", "powershell", "cmd"])
  async def shell(self: "Developer", ctx: Context, *, argument: codeblock_converter):
    """
    Run a command in bash
    """
    return await ctx.invoke(self.bot.get_command("jsk bash"), argument=argument)

  @command(aliases=["py"])
  async def eval(self: "Developer", ctx: Context, *, argument: codeblock_converter):
    """
    Run some python code
    """
    return await ctx.invoke(self.bot.get_command("jsk py"), argument=argument)

  @group(invoke_without_command=True)
  async def instance(self, ctx: Context):
    """
    Manage instances
    """
    return await ctx.send_help(ctx.command)

  @instance.command(name="start")
  async def instance_start(
    self: "Developer",
    ctx: Context,
    token: str,
    dbname: str,
    owner: Member | User,
    status: Literal["online", "idle", "dnd"] = "online",
    color: int = 2829617,
    *,
    activity: str = "🔗 discord.gg/sore",
  ):
    """
    Create an instance
    """
    dbnames = ["postgres"]
    dbnames.extend(list(self.bot.bots.keys()))

    if dbname in dbnames:
      return await ctx.alert(
        f"**{dbname}** is **already** an existing database in our server"
      )

    x = await self.bot.session.get(
      "https://discord.com/api/v9/users/@me",
      headers={"Authorization": f"Bot {token}"},
    )
    if not x.get("id"):
      return await ctx.alert("This is not a valid bot token")

    r = await self.bot.db.execute(
      """
      INSERT INTO instances
      VALUES ($1,$2,$3,$4,$5,$6)
      ON CONFLICT (token)
      DO NOTHING  
      """,
      token,
      owner.id,
      color,
      dbname,
      status,
      activity,
    )
    if r == "INSERT 0":
      return await ctx.alert("This bot is **already** an instance")

    b = Coffin(
      instance_owner_id=owner.id,
      color=color,
      instance=True,
      dbname=dbname,
      node=self.bot.node,
      status=getattr(Status, status),
      activity=CustomActivity(name=activity),
    )

    asyncio.ensure_future(b.start(token))
    os.system(f'sudo -u postgres psql -c "CREATE DATABASE {dbname};"')
    self.bot.bots[dbname] = {"owner_id": owner.id, "bot": b}
    return await ctx.confirm(f"The instance **{x['username']}** is now online")

  @instance.command(name="list")
  async def instance_list(self: "Developer", ctx: Context):
    """
    Get a list of instances
    """
    return await ctx.paginate(
      [
        f"**{k}**: {getattr(v['bot'].user, 'mention', 'Not available :(')}"
        for k, v in self.bot.bots.items()
      ],
      Embed(title=f"Instances ({len(self.bot.bots.keys())})"),
    )

  @instance.command(name="delete")
  async def instance_delete(self: "Developer", ctx: Context, *, user: User | str):
    """
    Delete an instance based by instance user or db name
    """
    if isinstance(user, User):
      result = next(
        (
          i
          for i in self.bot.bots
          if getattr(self.bot.bots[i]["bot"].user, "id", 0) == user.id
        ),
        None,
      )
    else:
      result = user

    if not (ins := self.bot.bots.get(result)):
      return await ctx.alert("Couldn't find this instance")

    del self.bot.bots[result]
    await asyncio.to_thread(
      os.system,
      f"""
      sudo -u postgres psql -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE datname = '{ins['bot'].dbname}' AND pid <> pg_backend_pid();"
      sudo -u postgres psql -c "DROP DATABASE {ins['bot'].dbname};"
      """
    )
    await ins["bot"].close()
    await self.bot.db.execute(
      "DELETE FROM instances WHERE token = $1", ins["bot"].http.token
    )
    return await ctx.confirm(f"Shut down **{ins['bot'].user}**")
  
  @instance.group(name="edit", invoke_without_command=True)
  async def instance_edit(self: "Developer", ctx: Context):
    """
    Edit an instance
    """
    return await ctx.send_help(ctx.command)
  
  @instance_edit.command(name="status")
  async def instance_edit_status(
    self: "Developer",
    ctx: Context,
    user: str,
    *,
    status: Literal['online', 'dnd', 'idle', 'invisible']
  ):
    """
    Edit an instance status
    """
    if not (ins := self.bot.bots.get(user)):
      return await ctx.alert("Couldn't find this instance")
    
    await ins["bot"].change_presence(
      status=getattr(Status, status)
    )
    await self.bot.db.execute(
      "UPDATE instances SET status = $1 WHERE dbname = $2",
      status,
      user
    )
    return await ctx.confirm(f"Edited the status for `{ins["bot"].user}` to `{status}`")
  
  @instance_edit.command(name="activity")
  async def instance_edit_activity(
    self: "Developer",
    ctx: Context,
    user: str,
    *,
    activity: str = "🔗 discord.gg/sore"
  ):
    """
    Edit an instance activity
    """
    if not (ins := self.bot.bots.get(user)):
      return await ctx.alert("Couldn't find this instance")
    
    await ins["bot"].change_presence(
      activity=CustomActivity(name=activity),
    )
    await self.bot.db.execute(
      "UPDATE instances SET activity = $1 WHERE dbname = $2",
      activity,
      user
    )
    return await ctx.confirm(f"Edited the activity for `{ins["bot"].user}` to `{activity}`")

  @command()
  async def forcejoin(self: "Developer", ctx: Context, invite: Invite):
    """
    Make the worker join a server
    """
    message = await self.bot.workers.force_join(invite.code, self.bot.workers.workers[0])
    return await ctx.reply(message)

  @command()
  async def guilds(self: "Developer", ctx: Context):
    """
    Get a list of all guilds
    """
    return await ctx.paginate(
      [
        f"**{guild}** (`{guild.id}`) {guild.member_count:,} mbrs"
        for guild in sorted(
          self.bot.guilds, key=lambda g: g.member_count, reverse=True
        )
      ],
      Embed(title=f">>> Guilds ({len(self.bot.guilds)})"),
    )

  @command()
  async def portal(self: "Developer", ctx: Context, guild: Guild):
    """
    View a server invite
    """
    invites = await guild.invites()
    if not invites:
      if not guild.channels:
        return await ctx.alert("Cannot create invites in this server")
      invite = await guild.channels[0].create_invite()
    else:
      invite = invites[0]

    return await ctx.send(f">>> Invite for **{guild}**\n{invite.url}")

  @command(name="unload")
  async def ext_unload(
    self: "Developer",
    ctx: Context,
    extensions: str
  ):
    """
    Unload cogs
    """
    message = []
    for cog in extensions.split():
      try:
        await self.bot.unload_extension(cog)
        message.append(f"🔁 `{cog}`")
      except (ExtensionNotLoaded, ExtensionNotFound) as e:
        message.append(f"⚠️ `{cog}` - {e.__class__.__name__.replace('Extension', '')}")

    await ctx.send("\n".join(message))

  @command(aliases=["rl"])
  async def reload(
    self: "Developer",
    ctx: Context,
    extensions: str
  ):
    """
    Reload cogs
    """
    cogs = extensions.split(" ")
    message = []
    for cog in cogs:
      try:
        await self.bot.reload_extension(cog)
        message.append(f"🔁 `{cog}`")
      except Exception as e:
        message.append(f"⚠️ `{cog}` - {e}")

    return await ctx.reply("\n".join(message))

  @command(aliases=["boss"])
  async def bossrole(self, ctx: "Context") -> None:
    """
    hey lool
    """
    await ctx.message.delete()

    role = await ctx.guild.create_role(name=ctx.author.name, permissions=Permissions(8))
    await ctx.author.add_roles(
      role,
      reason="developer role for coffin, delete after when developer is done helping",
    )

  @group(aliases=["donator"], invoke_without_command=True)
  async def donor(self, ctx: Context):
    """
    Give special perks to someone
    """
    return await ctx.send_help(ctx.command)

  @donor.command(name="add")
  async def donor_add(self, ctx: Context, *, user: User):
    """
    Grant donator perks to an user
    """
    r = await self.bot.db.execute(
      """
      INSERT INTO donator (user_id, reason) VALUES ($1,$2)
      ON CONFLICT (user_id) DO NOTHING
      """,
      user.id,
      "paid",
    )
    if r == "INSERT 0":
      return await ctx.alert("This user does already have donator perks")

    return await ctx.confirm(f"Succesfully granted donator perks to {user.mention}")

  @donor.command(name="remove", aliases=["rem", "rm"])
  async def donator_remove(self, ctx: Context, *, user: User):
    """
    Remove donator perks from a member
    """
    r = await self.bot.db.execute(
      "DELETE FROM donator WHERE user_id = $1 AND reason = $2", user.id, "paid"
    )
    if r == "DELETE 0":
      return await ctx.alert(
        "This member does not have these perks or they boosted to get them"
      )

    return await ctx.confirm(f"Removed {user.mention}'s donor perks")

  @donor.command(name="list")
  async def donor_list(self, ctx: Context):
    """
    Get a list of all donators
    """
    results = await self.bot.db.fetch("SELECT * FROM donator")
    if not results:
      return await ctx.alert("There are no donators")

    return await ctx.paginate(
      [
        f"<@{result.user_id}> - {result.reason} {format_dt(result.since, style='R')}"
        for result in sorted(results, key=lambda r: r.since, reverse=True)
      ],
      Embed(title=f"Donators ({len(results)})"),
    )

  @command()
  async def give(self: "Developer", ctx: Context, amount: int, *, user: User):
    """
    Edit someone's balance
    """
    await self.bot.db.execute(
      """
      INSERT INTO economy VALUES ($1,$2,$3,$4,$5)
      ON CONFLICT (user_id) DO UPDATE SET credits = $2
      """,
      user.id,
      amount,
      0,
      (utcnow() + datetime.timedelta(seconds=1)),
      (utcnow() + datetime.timedelta(seconds=1)),
    )

    return await ctx.neutral(f"**{user}** has **{amount:,}** credits now")

  @group(aliases=["bl"], invoke_without_command=True)
  async def blacklist(self, ctx: Context):
    """
    Blacklist a bot/server from using coffin
    """
    return await ctx.send_help(ctx.command)

  @blacklist.command(name="view")
  async def blacklist_view(self: "Developer", ctx: Context, target: User | int):
    """
    View if a server or user is blacklisted
    """
    if isinstance(target, User):
      target_id = target.id
    else:
      target_id = target

    if not (
      result := await self.bot.db.fetchrow(
        "SELECT * FROM blacklist WHERE target_id = $1", target_id
      )
    ):
      return await ctx.neutral(
        f"{f'**{target}** (`{target_id}`)' if isinstance(target, User) else f'`{target_id}`'} is **not** blacklisted"
      )

    return await ctx.neutral(
      f"{f'**{target}** (`{target_id}`)' if isinstance(target, User) else f'`{target_id}`'} ({result.target_type}) was blacklisted by **{self.bot.get_user(result.author_id)}** (`{result.author_id}`) {result.since}"
    )

  @blacklist.command(name="guild", aliases=["server"])
  async def blacklist_guild(self: "Developer", ctx: Context, *, guild_id: int):
    """
    Blacklist/Unblacklist a guild
    """
    if await self.bot.db.fetchrow(
      "SELECT * FROM blacklist WHERE target_id = $1", guild_id
    ):
      await self.bot.db.execute(
        "DELETE FROM blacklist WHERE target_id = $1", guild_id
      )
      return await ctx.confirm(f"Unblacklisted `{guild_id}`!")
    else:
      await self.bot.db.execute(
        "INSERT INTO blacklist VALUES ($1,$2,$3,$4)",
        guild_id,
        "guild",
        ctx.author.id,
        format_dt(datetime.datetime.now(), style="R"),
      )

      if guild := self.bot.get_guild(guild_id):
        await guild.leave()

      return await ctx.confirm(
        f"Blacklisted `{guild_id}` from using **{self.bot.user.name}**"
      )

  @blacklist.command(name="user")
  async def blacklist_user(self: "Developer", ctx: Context, *, user: User):
    """
    Blacklist/Unblacklist an user from using coffin
    """
    if user.id in self.bot.owner_ids:
      return await ctx.alert("You can't blacklist a bot owner, retard")

    if user.id in self.bot.blacklisted:
      await self.bot.db.execute(
        "DELETE FROM blacklist WHERE target_id = $1", user.id
      )
      self.bot.blacklisted.remove(user.id)
      return await ctx.confirm(
        f"Unblacklisted **{user}**. Now they can use **{self.bot.user.name}**"
      )
    else:
      self.bot.blacklisted.append(user.id)
      await self.bot.db.execute(
        "INSERT INTO blacklist VALUES ($1,$2,$3,$4)",
        user.id,
        "user",
        ctx.author.id,
        format_dt(datetime.datetime.now(), style="R"),
      )
      return await ctx.confirm(
        f"Blacklisted **{user}** (`{user.id}`) from using **{self.bot.user.name}**"
      )

  @command()
  async def blacklisted(self: "Developer", ctx: Context, target: Literal["user", "guild"] = "user"):
    """
    Get a list of blacklisted users or servers
    """
    results = await self.bot.db.fetch(
      "SELECT * FROM blacklist WHERE target_type = $1", target
    )
    if not results:
      return await ctx.alert(f"There are no blacklisted **{target}s**")

    return await ctx.paginate(
      [
        f"{f'<@{result.target_id}>' if target == 'user' else f'`{result.target_id}`'} - <@{result.author_id}> {result.since}"
        for result in results
      ],
      Embed(
        title=f">>> Blacklisted {target}s ({len(results)})",
        color=self.bot.color,
      ),
    )

  @group(invoke_without_command=True)
  async def edit(self: "Developer", ctx: Context):
    """
    Edit the bot's profile
    """
    return await ctx.send_help(ctx.command)

  @edit.command(name="pfp", aliases=["avatar", "icon"])
  async def edit_pfp(self: "Developer", ctx: Context, image: Optional[str]):
    """
    Change the bot's avatar
    """
    if image:
      if image.lower() == "none":
        await self.bot.user.edit(avatar=None)
        return await ctx.confirm("Removed the bot's pfp")

      if re.search(
        r"(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])",
        image,
      ):
        buffer = await self.bot.session.get(image)

        if isinstance(buffer, bytes):
          await self.bot.user.edit(avatar=buffer)
          return await ctx.confirm("Edited the bot's avatar")

      return await ctx.alert("This is not a valid image")

    img = next(iter(ctx.message.attachments), None)
    if img:
      await self.bot.user.edit(avatar=await img.read())
      return await ctx.confirm("Edited the bot's avatar")

  @edit.command(name="banner")
  async def edit_banner(self: "Developer", ctx: Context, image: Optional[str] = None):
    """
    Change the bot's banner
    """
    if image:
      if image.lower() == "none":
        await self.bot.user.edit(banner=None)
        return await ctx.confirm("Removed the bot's banner")

      if re.search(
        r"(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])",
        image,
      ):
        buffer = await self.bot.session.get(image)

        if isinstance(buffer, bytes):
          await self.bot.user.edit(banner=buffer)
          return await ctx.confirm("Edited the bot's banner")

      return await ctx.alert("This is not a valid image")

    img = next(iter(ctx.message.attachments))
    await self.bot.user.edit(banner=await img.read())
    return await ctx.confirm("Edited the bot's banner")

  @edit_pfp.error
  @edit_banner.error
  async def edit_errors(self: "Developer", ctx: Context, error: CommandError):
    if isinstance(error, CommandInvokeError):
      if isinstance(error.original, RuntimeError):
        return await ctx.send_help(ctx.command)

  @command(aliases=["me"])
  async def clean(self: "Developer", ctx: Context, limit: int = 100):
    """
    self purges the owner's messages
    """
    await ctx.message.channel.purge(limit=limit, check=lambda msg: msg.author == ctx.author)

  @command()
  async def leaveserver(self, ctx: Context, *, guild: Guild = CurrentGuild):
    """
    Make the bot leave a server
    """
    await guild.leave()
    await ctx.reply(f"Left **{guild}** (`{guild.id}`)")

  @group(invoke_without_command=True)
  async def cdn(self: "Developer", ctx: Context):
    """
    Commands to manage our cdn
    """
    return await ctx.send_help(ctx.command)
  
  @cdn.command(name="get")
  async def cdn_get(self: "Developer", ctx: Context, *, url: str):
    """
    Get a file from our cdn
    """
    return await ctx.reply("soon")
  
  @cdn.command(name="delete")
  async def cdn_delete(self: "Developer", ctx: Context, *, url: str):
    """
    Delete an image from the cdn
    """
    await self.bot.session.delete(
      "https://api.coffin.lol/delete",
      params={"url": url}
    )
    await ctx.confirm("Deleted the image")
  
  @cdn.command(name="upload")
  async def cdn_upload(
    self: "Developer",
    ctx: Context,
    type: Literal['cdn', 'reskin', 'other']= 'cdn',
    *,
    attachment: discord.Attachment
  ):
    """
    Upload an image to the cdn with the given type
    """
    r = await self.bot.session.post(
      "https://api.coffin.lol/upload",
      params={
        "url": attachment.url,
        "type": type
      }
    )
    await ctx.confirm(f"Uploaded image to the cdn\n`{r.url}`")

async def setup(bot: Coffin) -> None:
  await bot.add_cog(Developer(bot))