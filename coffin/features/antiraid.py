import json
import asyncio
import datetime

from collections import defaultdict
from humanfriendly import format_timespan

from discord import (
  Member,
  utils,
  Embed,
  TextChannel,
  Interaction
)
from discord.ext.commands import (
  Cog,
  group,
  has_permissions,
  ChannelNotFound
)
from typing import (
  Literal,
  Union
)

from structure import (
  Context,
  Coffin,
  getLogger,
  Time
)

logger = getLogger(__name__)

class Antiraid(Cog):
  """
  Protect ur server from raiders
  """
  def __init__(self: "Antiraid", bot: Coffin):
    self.bot = bot
    self.locks = defaultdict(asyncio.Lock)
    self.massjoin_cache = defaultdict(list)

  async def punish(
    self: "Antiraid",
    member: Member,
    punishment: str,
    reason: str,
    logs: TextChannel = None,
  ):
    match punishment:
      case "kick":
        await member.kick(reason=reason)
      case "ban":
        await member.ban(reason=reason)
      case _:
        pass

    await self.send_report(
      member=member,
      logs=logs,
      reason=reason
    )
  
  async def send_report(
    self: "Antiraid",
    member: Member,
    logs: TextChannel,
    reason: str
  ):
    embed = (
      Embed(
        color=self.bot.color,
        title="Member punished",
      )
      .set_author(name=member.guild.name, icon_url=member.guild.icon)
      .add_field(
        name="User", value=f"**{member}** (`{member.id}`)", inline=False
      )
      .add_field(
        name="Reason", value=reason, inline=False
      )
    )
    if channel := logs:
      return await channel.send(embed=embed)
  
  @Cog.listener("on_member_join")
  async def massjoin(self: "Antiraid", member: Member):
    result = await self.bot.db.fetchrow(
      "SELECT * FROM antiraid WHERE guild_id = $1", member.guild.id
    )
    if not result or not (
      modules := json.loads(result["modules"]).get("massjoin")
    ):
      return

    self.massjoin_cache[member.guild.id].append(
      [utils.utcnow().replace(tzinfo=None), member.id]
    )
    expired = [
      mem
      for mem in self.massjoin_cache[member.guild.id]
      if (utils.utcnow().replace(tzinfo=None) - mem[0]).total_seconds() > modules["time"]
    ]
    for m in expired:
      self.massjoin_cache[member.guild.id].remove(m)

    if len(self.massjoin_cache[member.guild.id]) > modules["rate"]:
      async with self.locks[member.guild.id]:
        members = [m[1] for m in self.massjoin_cache[member.guild.id]]
        logs = member.guild.get_channel(result["logs"])
        task = [
          self.punish(
            member=member.guild.get_member(m),
            punishment=modules["punishment"],
            reason="Antiraid: Mass join detected",
            logs=logs
          )
          for m in members
        ]
        await member.guild.edit(
          dms_disabled_until=(utils.utcnow() + datetime.timedelta(seconds=modules["pause"]) if modules["pause"] else None),
          invites_disabled_until=(utils.utcnow() + datetime.timedelta(seconds=modules["pause"]) if modules["pause"] else None),
        )
        await self.bot.db.execute(
          "UPDATE antiraid SET lockdown = $1 WHERE guild_id = $2",
          True, member.guild.id
        )
        await asyncio.gather(*task)
 
  @Cog.listener("on_member_join")
  async def noavatar(self: "Antiraid", member: Member):
    if not member.avatar:
      result = await self.bot.db.fetchrow(
        "SELECT * FROM antiraid WHERE guild_id = $1",
        member.guild.id
      )
      if not result or not (
        module := json.loads(result["modules"]).get("noavatar")
      ):
        return

      if (
        whitelisted := json.loads(result["whitelisted"]).get("noavatar")
      ):
        if member.id in whitelisted:
          return

      async with self.locks[member.guild.id]:
        logs = member.guild.get_channel(result["logs"])
        await self.punish(
          member=member,
          punishment=module["punishment"],
          reason="Antiraid: Member doesn't have an avatar",
          logs=logs
        )
  
  @Cog.listener("on_member_join")
  async def newaccount(self: "Antiraid", member: Member):
    result = await self.bot.db.fetchrow(
      "SELECT * FROM antiraid WHERE guild_id = $1", member.guild.id
    )
    if not result or not (
      modules := json.loads(result["modules"]).get("newaccount")
    ):
      return
    
    if (
      whitelisted := json.loads(result["whitelisted"]).get("newaccount")
    ):
      if member.id in whitelisted:
        return
    
    async with self.locks[member.guild.id]:
      age = (
        utils.utcnow().replace(tzinfo=None) - member.created_at.replace(tzinfo=None)
      ).total_seconds()

      if age < modules["time"]:
        logs = member.guild.get_channel(result["logs"])
        await self.punish(
          member=member,
          punishment=modules["punishment"],
          reason="Antiraid: Account to young to be on this server",
          logs=logs
        )
 
  @group(invoke_without_command=True)
  async def antiraid(self: "Antiraid", ctx: Context):
    """
    Antiraid commands
    """
    return await ctx.send_help(ctx.command)
  
  @antiraid.command(
    name="enable",
    aliases=["e"]
  )
  @has_permissions(manage_guild=True)
  async def antiraid_enable(self: "Antiraid", ctx: Context):
    """
    Enable the antiraid protection
    """
    await self.bot.db.execute(
      """
      INSERT INTO antiraid (guild_id) VALUES ($1)
      ON CONFLICT (guild_id) DO NOTHING
      """,
      ctx.guild.id
    )
    return await ctx.confirm("Enabled the antiraid protection")
  
  @antiraid.command(
    name="disable",
    aliases=["d"]
  )
  @has_permissions(manage_guild=True)
  async def antiraid_disable(self: "Antiraid", ctx: Context):
    """
    Disable the antiraid protection
    """
    async def yes(interaction: Interaction):
      embed = interaction.message.embeds[0]
      await interaction.client.db.execute(
        "DELETE FROM antiraid WHERE guild_id = $1", interaction.guild.id
      )

      embed.description = "Disabled the antiraid protection"
      return await interaction.response.edit_message(embed=embed, view=None)
    
    return await ctx.confirmation(
      "Are you sure you want to disable the antiraid feature? This will erase **ALL** configurations for this feature",
      yes
    )

  @antiraid.command(name="lockdown")
  @has_permissions(manage_guild=True)
  async def antiraid_lockdown(self: "Antiraid", ctx: Context):
    """
    Disable the server's antiraid lockdown
    """
    if await self.bot.db.fetchval(
      "SELECT lockdown FROM antiraid WHERE guild_id = $1",
      ctx.guild.id
    ) is False:
      return await ctx.alert("The antiraid lockdown hasn't been triggered")
    
    await self.bot.db.execute(
      "UPDATE antiraid SET lockdown = $1 WHERE guild_id = $2",
      False,
      ctx.guild.id
    )
    await ctx.guild.edit(
      dms_disabled_until=None,
      invites_disabled_until=None
    )
    return await ctx.confirm("The antiraid lockdown state has been disabled")

  @antiraid.command(name="whitelist")
  @has_permissions(manage_guild=True)
  async def antiraid_whitelist(
    self: "Antiraid",
    ctx: Context,
    module: Literal["avatar", "account"],
    *,
    member: Member
  ):
    """
    Whitelist a member for certain antiraid modules
    """
    if not (
      whitelisted := await self.bot.db.fetchval(
        "SELECT whitelisted FROM antiraid WHERE guild_id = $1", ctx.guild.id
      )
    ):
      return await ctx.alert("Antiraid has **not** been enabled. Please use the `antiraid enable` command to enable it")
    
    whitelist = json.loads(whitelisted)
    if not module in whitelist:
      whitelist[module] = []

    if member.id in whitelist[module]:
      whitelist[module].remove(member.id)
      message = f"**{member}** is **not** whitelited for `{module}` anymore"
    else:
      whitelist[module].append(member.id)
      message = f"**{member}** is whitelisted from `{module}`"
    
    await self.bot.db.execute(
      "UPDATE antiraid SET whitelisted = $1 WHERE guild_id = $2",
      json.dumps(whitelist),
      ctx.guild.id
    )
    return await ctx.confirm(message)

  @antiraid.command(name="whitelisted")
  @has_permissions(manage_guild=True)
  async def antiraid_whitelisted(
    self: "Antiraid",
    ctx: Context,
    module: Literal["avatar", "account"]
  ):
    """
    Get a list of all whitelisted people
    """
    whitelisted = await self.bot.db.fetchval("SELECT whitelisted FROM antiraid WHERE guild_id = $1", ctx.guild.id)
    if not whitelisted:
      return await ctx.alert("There are no whitelisted members!")
    
    whitelist: dict = json.loads(whitelisted)
    if not whitelist.get(module, []):
      return await ctx.alert(f"No one is whitelisted for `{module}`")

    return await ctx.paginate(
      [
        f"<@{i}> (`{i}`)"
        for i in sorted(
          whitelist[module], key=lambda m: ctx.guild.get_member(m) is not None
        )
      ],
      Embed(title=f"Antiraid whitelisted in {ctx.guild.name}")
    )

  @antiraid.command(name="settings")
  @has_permissions(manage_guild=True)
  async def antiraid_settings(self, ctx: Context):
    """
    Check the antiraid module settings
    """
    result = await self.bot.db.fetchrow("SELECT * FROM antiraid WHERE guild_id = $1", ctx.guild.id)
    if not result:
      return await ctx.alert(
        "Antiraid has **not** been enabled. Please use the `antiraid enable` command"
      )

    modules: dict = json.loads(result["modules"])
    channel = ctx.guild.get_channel(result["logs"])

    if len(list(modules.keys())) == 0 and not channel:
      return await ctx.alert("There are no antiraid modules enabled")

    embed = Embed(
      color=self.bot.color,
      title="Antiraid Settings",
      description="\n".join(
        [
          f"<:check:1334239511269605437> {a} - {p.get('punishment')} {f'threshold: {p.get('time')}' if a in ['avatar', 'account'] else ''} {f'rate: {p.get('rate')}' if a in ['massjoin'] else ''}"
          for a, p in modules.items()
        ]
      ),
    ).set_author(name=ctx.guild.name, icon_url=ctx.guild.icon)

    if channel:
      embed.add_field(
        name="Logs channel", value=f"{channel.mention} (`{channel.id}`)"
      )

    return await ctx.send(embed=embed)
  
  @antiraid.command(name="logs")
  @has_permissions(manage_guild=True)
  async def antiraid_logs(
    self: "Antiraid",
    ctx: Context,
    channel: Union[TextChannel, str]
  ):
    """
    Configure your antiraid logs
    """
    if isinstance(channel, str):
      if channel.lower() == "none":
        await self.bot.db.execute(
          "UPDATE antiraid SET logs = $1 WHERE guild_id = $2",
          None,
          ctx.guild.id,
        )
        return await ctx.confirm("Removed antiraid logs")
      else:
        raise ChannelNotFound(channel)
    else:
      await self.bot.db.execute(
        "UPDATE antiraid SET logs = $1 WHERE guild_id = $2",
        channel.id,
        ctx.guild.id,
      )
      await ctx.confirm(
        f"Antiraid log channel was configured succesfully to {channel.mention}"
      )
 
  @antiraid.command(name="avatar")
  @has_permissions(manage_guild=True)
  async def antiraid_avatar(
    self: "Antiraid",
    ctx: Context,
    punishment: Literal["kick", "ban", "none"]
  ):
    """
    Enable the antiraid default avatar protection
    """
    if not (
      modules := await self.bot.db.fetchval(
        "SELECT modules FROM antiraid WHERE guild_id = $1", ctx.guild.id
      )
    ):
      return await ctx.alert("Antiraid has **not** been enabled. Please use the `antiraid enable` command to enable it")
    
    modules = json.loads(modules)
    if punishment != "none":
      modules["noavatar"] = {"punishment": punishment}
      await ctx.confirm(f"Antiraid **default avatar** is now enabled - `{punishment}`")
    else:
      if modules.get("noavatar"):
        modules.pop("noavatar")
        await ctx.confirm("Antiraid **default avatar** is now disabled")
      else:
        return await ctx.alert("Antiraid **default avatar** has not been enabled")
      
    await self.bot.db.execute(
      "UPDATE antiraid SET modules = $1 WHERE guild_id = $2",
      json.dumps(modules),
      ctx.guild.id
    )
  
  @antiraid.command(name="account", example="kick 7d")
  @has_permissions(manage_guild=True)
  async def antiraid_account(
    self: "Antiraid",
    ctx: Context,
    punishment: Literal["kick", "ban", "none"],
    threshold: Time = "3d"
  ):
    """
    Enable the antiraid account age protection
    """
    if not (
      modules := await self.bot.db.fetchval(
        "SELECT modules FROM antiraid WHERE guild_id = $1", ctx.guild.id
      )
    ):
      return await ctx.alert("Antiraid has **not** been enabled. Please use the `antiraid enable` command to enable it")
    
    modules = json.loads(modules)
    if punishment != "none":
      modules["newaccount"] = {"punishment": punishment, "time": int(threshold)}
      await ctx.confirm(f"Antiraid **new accounts** is now enabled - `{punishment}`\nAccount age: `{format_timespan(threshold)}`")
    else:
      if modules.get("newaccount"):
        modules.pop("newaccount")
        await ctx.confirm("Antiraid **new accounts** is now disabled")
      else:
        return await ctx.alert("Antiraid **new accounts** has not been enabled")
      
    await self.bot.db.execute(
      "UPDATE antiraid SET modules = $1 WHERE guild_id = $2",
      json.dumps(modules),
      ctx.guild.id
    )
  
  @antiraid.command(name="massjoin", example="kick 10m 8")
  @has_permissions(manage_guild=True)
  async def antiraid_massjoin(
    self: "Antiraid",
    ctx: Context,
    punishment: Literal["kick", "ban", "none"],
    threshold: Time = "10s",
    joins: int = 5,
    pause: Time = None
  ):
    """
    Enable the antiraid mass join protection
    """
    if not (
      modules := await self.bot.db.fetchval(
        "SELECT modules FROM antiraid WHERE guild_id = $1", ctx.guild.id
      )
    ):
      return await ctx.alert("Antiraid has **not** been enabled. Please use the `antiraid enable` command to enable it")

    if joins <= 0:
      return await ctx.alert("The number of joins cant be below `0`")
    
    if pause and int(pause) > 86400:
      return await ctx.alert("Time cant be above `24 hours`")

    modules = json.loads(modules)
    if punishment != "none":
      modules["massjoin"] = {"punishment": punishment, "time": int(threshold), "rate": joins, "pause": int(pause) if pause else None}
      await ctx.confirm(
        f"Antiraid **massjoin** is now enabled - `{punishment}`\nRate: `{joins}` joins per `{format_timespan(threshold)}` {f'\nPausing dms & invites for `{format_timespan(pause)}`' if pause else ''}"
      )
    else:
      if modules.get("massjoin"):
        modules.pop("massjoin")
        await ctx.confirm("Antiraid **massjoin** is now disabled")
      else:
        return await ctx.alert("Antiraid **massjoin** has not been enabled")
      
    await self.bot.db.execute(
      "UPDATE antiraid SET modules = $1 WHERE guild_id = $2",
      json.dumps(modules),
      ctx.guild.id
    )

async def setup(bot: Coffin):
  return await bot.add_cog(Antiraid(bot))