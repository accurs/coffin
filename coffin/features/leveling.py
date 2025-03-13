import secrets
import discord 
import asyncio

from discord.ext import commands 
from contextlib import suppress
from collections import defaultdict

from structure import (
  Coffin,
  Context,
  AssignableRole
)
from typing import (
  List,
  Union,
  Annotated
)

class Leveling(commands.Cog):
  """
  You type u get xp u level
  """
  def __init__(self, bot: Coffin):
    self.bot = bot 
    self.locks = defaultdict(asyncio.Lock)
    self.cache = {}
  
  async def remove_item(self, message: discord.Message):
    await asyncio.sleep(1.9)
    with suppress(KeyError | ValueError):
      self.cache[message.author.id].remove(message)
  
  async def update_roles(self, member: discord.Member, level: int):
    results = await self.bot.db.fetch(
      """
      SELECT * FROM leveling.roles
      WHERE guild_id = $1
      AND level_required <= $2 
      """,
      member.guild.id, level
    ) or []

    for result in results: 
      if role := member.guild.get_role(result.role_id):
        if role.is_assignable():
          await asyncio.sleep(0.01)
          await member.add_roles(role, reason=f"Member leveled up to level {result.level_required}")

  @commands.Cog.listener()
  async def on_message(self, message: discord.Message):
    if message.guild and not message.author.bot: 
      cache: List[discord.Message] = self.cache.get(message.author.id, [])
      if len(cache) < 5:
        async with self.locks[message.channel.id]:
          if config := await self.bot.db.fetchrow("SELECT * FROM leveling.config WHERE guild_id = $1", message.guild.id):
            cache.append(message)
            self.cache[message.author.id] = cache 
            asyncio.ensure_future(self.remove_item(message))
            xp = secrets.choice(range(1, 10))
            
            multiplier = await self.bot.db.fetchrow(
              """
              SELECT * FROM leveling.multiplier
              WHERE guild_id = $1""",
              message.guild.id
            )
            
            donator = await self.bot.db.fetchval(
              "SELECT user_id FROM donator WHERE user_id = $1",
              message.author.id
            )
            if donator:
              xp += 4

            result = await self.bot.db.fetchrow(
              """
              INSERT INTO leveling.members (guild_id, user_id, xp)
              VALUES ($1,$2,$3) ON CONFLICT 
              (guild_id, user_id) DO UPDATE SET
              xp = leveling.members.xp + $3
              RETURNING lvl, xp, target_xp 
              """,
              message.guild.id, message.author.id,
              xp
            ) 

            level: int = result.lvl
            if result.xp >= result.target_xp:
              level += 1
              target_xp: int = 500*level/2
              xp = 0

              await self.bot.db.execute(
                """
                UPDATE leveling.members SET
                target_xp = $1, xp = $2, 
                lvl = $3 WHERE user_id = $4
                AND guild_id = $5 
                """,
                target_xp, xp, level, 
                message.author.id,
                message.guild.id
              )
                
              script = await self.bot.embed.convert(
                message.author, 
                config.level_message, 
                {'level': level}
              )
              script.pop('delete_after', None)

              if channel := message.guild.get_channel(config.channel_id):
                await channel.send(**script)
              else:
                await message.channel.send(**script) 
            
            await self.update_roles(message.author, level)
  
  @commands.hybrid_command()
  async def rank(
    self, 
    ctx: Context, 
    *,
    member: discord.Member = commands.Author
  ):
    """
    Check someone's level
    """
    result = await self.bot.db.fetchrow(
      """
      SELECT * FROM leveling.members
      WHERE guild_id = $1
      AND user_id = $2 
      """,
      ctx.guild.id,
      member.id
    )

    if result:
      level: int = result.lvl
      target_xp: int = result.target_xp 
      xp: int = result.xp
    else:
      level: int = 0
      target_xp: int = 250
      xp: int = 0

    embed = (
      discord.Embed(
        color=self.bot.color,
        title=f"{member.display_name}'s rank"
      )
      .set_author(
        name=member.name,
        icon_url=member.display_avatar.url
      )
      .add_field(
        name="Level",
        value=f"`{level}`",
        inline=False
      )
      .add_field(
        name="XP",
        value=f"{xp}/{target_xp} (`{round(xp/target_xp*100)}%`)"
      )
    )

    return await ctx.reply(embed=embed)
  
  @commands.group(invoke_without_command=True)
  async def level(self, ctx: Context):
    """
    Get xp points while you chat
    """
    return await ctx.send_help(ctx.command)
  
  @level.command(name="enable")
  @commands.has_permissions(manage_guild=True)
  async def level_enable(self, ctx: Context):
    """
    Enable the leveling system for this server
    """
    status = await self.bot.db.execute(
      """
      INSERT INTO leveling.config (guild_id)
      VALUES ($1) ON CONFLICT (guild_id)
      DO NOTHING  
      """,
      ctx.guild.id
    )
    if status == "INSERT 0":
      return await ctx.alert("Leveling is **already** enabled")
    
    return await ctx.confirm("Enabled the leveling feature")
  
  @level.command(
    name="disable",
    aliases=[
        'dis', 
        'rm',
        'remove'
    ]
  )
  @commands.has_permissions(manage_guild=True)
  async def level_disable(self, ctx: Context):
    """
    Disable the leveling system in this server
    """
    async def yes(interaction: discord.Interaction):
      await self.bot.db.execute(
        """
        DELETE FROM leveling.config WHERE guild_id = $1;
        """,
        interaction.guild.id
      )
      await self.bot.db.execute(
        """
        DELETE FROM leveling.members WHERE guild_id = $1;
        """,
        interaction.guild.id
      )
      await self.bot.db.execute(
        """
        DELETE FROM leveling.roles WHERE guild_id = $1;
        """,
        interaction.guild.id
      )

      embed = interaction.message.embeds[0]
      embed.description = "Succesfully disabled the leveling feature"
      await interaction.response.edit_message(
        embed=embed,
        view=None
      )
    
    return await ctx.confirmation(
      "Are you sure you want to **disable** the leveling feature? This will clear all configurations and members' progress",
      yes
    )
  
  @level.command(name="channel")
  @commands.has_permissions(manage_guild=True)
  async def level_channel(
    self, 
    ctx: Context,
    *,
    channel: Union[discord.TextChannel, str]
  ):
    """
    Assign a channel where to notify members when they level up. It can be none
    """
    if isinstance(channel, str):
      if channel.lower() == "none":
        channel = None 
      else:
        raise commands.ChannelNotFound(channel)
    
    channel_id = await self.bot.db.fetchval(
      """
      UPDATE leveling.config SET
      channel_id = $1
      WHERE guild_id = $2
      RETURNING channel_id  
      """,
      getattr(channel, "id", None),
      ctx.guild.id
    )
    
    if not channel_id:
      return await ctx.confirm("Removed the leveling channel")
    else:
      return await ctx.confirm(f"Assigned <#{channel_id}> as the leveling channel")
  
  @level.command(
    name="message",
    aliases=['msg'],
    example=";level message {user.mention} reached level {level}"
  )
  @commands.has_permissions(manage_guild=True)
  async def level_message(
    self, 
    ctx: Context,
    *,
    message: str
  ):
    """
    Update the level up message
    """
    await self.bot.db.execute(
      """
      UPDATE leveling.config SET
      level_message = $1
      WHERE guild_id = $2  
      """,
      message, ctx.guild.id
    )

    return await ctx.confirm("Successfully updated the level message")
  
  @level.command(name="test")
  @commands.has_permissions(manage_guild=True)
  async def level_test(
    self,
    ctx: Context
  ):
    """
    Test the level up message
    """
    if not (result := await self.bot.db.fetchrow("SELECT * FROM leveling.config WHERE guild_id = $1", ctx.guild.id)):
      return await ctx.alert("Leveling feature is **not** enabled")
    
    script = await self.bot.embed.convert(ctx.author, result.level_message, {"level": 0})
    script.pop('delete_after', None)

    if channel := ctx.guild.get_channel(result.channel_id):
      await channel.send(**script)
    else:
      await ctx.send(**script)
  
  @level.command(
    name="settings",
    aliases=['stats']
  )
  @commands.has_permissions(manage_guild=True)
  async def level_settings(self, ctx: Context):
    """
    Check the settings for the leveling feature
    """
    config = await self.bot.db.fetchrow(
      """
      SELECT * FROM leveling.config
      WHERE guild_id = $1 
      """,
      ctx.guild.id
    )

    if not config:
      return await ctx.alert("Leveling feature is **not** enabled")
    
    embed = (
      discord.Embed(
        title="Leveling setings"
      )
      .set_author(
        name=ctx.guild.name,
        icon_url=ctx.guild.icon
      )
      .add_field(
        name="Leveling channel",
        value=getattr(ctx.guild.get_channel(config.channel_id), "mention", "Message Reply"),
        inline=False
      )
      .add_field(
        name="Leveling message",
        value=f"```{config.level_message}```"
    )
    )

    return await ctx.reply(embed=embed)
  
  @level.group(name="roles", invoke_without_command=True)
  async def level_roles(self, ctx: Context):
    """
    Add role rewards for leveling up
    """
    return await ctx.send_help(ctx.command)

  @level_roles.command(name="add")
  @commands.has_permissions(manage_guild=True)
  async def level_roles_add(
    self,
    ctx: Context,
    level: int,
    *,
    role: Annotated[discord.Role, AssignableRole]
  ):
    """
    Add a leveling reward
    """
    if level < 1 or level >= 2147483647:
      return await ctx.alert("This is an invalid number for the level")
    
    await self.bot.db.execute(
      """
      INSERT INTO leveling.roles VALUES ($1,$2,$3)
      ON CONFLICT (guild_id, role_id) 
      DO UPDATE SET level_required = $3   
      """,
      ctx.guild.id, role.id, level
    )

    return await ctx.confirm(f"{role.mention} will be granted to members if they reach level **{level}**")

  @level_roles.command(
    name="remove",
    aliases=['rm']
  )
  @commands.has_permissions(manage_guild=True)
  async def level_roles_remove(
    self,
    ctx: Context,
    level: int
  ):
    """
    Remove the reward from a certain level
    """
    status = await self.bot.db.execute(
      """
      DELETE FROM leveling.roles
      WHERE guild_id = $1
      AND level_required = $2   
      """,
      ctx.guild.id, level
    )
    if status == "DELETE 0":
      return await ctx.alert(f"There's no reward at level **{level}**")
    else:
      return await ctx.confirm(f"Removed the reward from level **{level}**")
  
  @level_roles.command(
    name="view",
    aliases=['list']
  )
  async def level_roles_view(
    self,
    ctx: Context
  ):
    """
    View all leveling rewards
    """
    results = await self.bot.db.fetch(
      """
      SELECT role_id, level_required FROM leveling.roles
      WHERE guild_id = $1 ORDER BY level_required ASC   
      """,
      ctx.guild.id
    )
    if not results:
      return await ctx.alert("There are no leveling rewards")
    
    return await ctx.paginate(
      [
        f"<@{result.role_id}> at level **{result.level_required}**"
        for result in results 
      ],
      discord.Embed(title=f"Leveling rewards ({len(results)})")
    )

  @level.command(
    name="leaderboard",
    aliases=['lb']
  )
  async def level_leaderboard(
    self,
    ctx: Context
  ):
    """
    Get top 10 members with the highest level
    """
    results = await self.bot.db.fetch(
      """
      SELECT * FROM leveling.members
      WHERE guild_id = $1
      ORDER BY lvl DESC,
      xp DESC LIMIT 10  
      """,
      ctx.guild.id
    )
    if not results:
      return await ctx.alert("Unable to show the leaderboard")
    
    return await ctx.paginate(
      [
        f"<@{result.user_id}> is level `{result.lvl}` (`{result.xp}` xp)"
        for result in results
      ],
      discord.Embed(title="Top 10 Leveling leaderboard")
    )
  
  """@level.group(name="multiplier", invoke_without_command=True)
  async def level_multiplier(
    self,
    ctx: Context
  ):
    "
    Add a multiplier for a role
    "
    return await ctx.send_help(ctx.command)
  
  @level_multiplier.command(name="add")
  @commands.has_permissions(manage_guild=True)
  async def levelmultiplier_add(
    self,
    ctx: Context,
    role: AssignableRole,
    *,
    multiply: int
  ):
    "
    Multiply the xp that u get if u have a certain role
    "
    if multiply >= 5:
      return await ctx.alert("U cant multiply the xp more than 5")
    
    roles = (
      await self.bot.db.fetchval(
        "SELECT roles FROM leveling.multiplier WHERE guild_id = $1",
        ctx.guild.id
      )
      or []
    )
    
    if role.id in roles:
      return await ctx.alert("This role is already being multiplied")
    
    roles.append(role.id)
    await self.bot.db.execute(
      "
      INSERT INTO leveling.multiplier VALUES ($1,$2,$3)
      ON CONFLICT (guild_id) DO UPDATE
      SET roles = $2, multiplier = $3",
      ctx.guild.id,
      roles,
      multiply
    )
    return await ctx.confirm(f"Multipling {role.mention}'s xp by `{multiply}`")"""

async def setup(bot: Coffin) -> None:
  return await bot.add_cog(Leveling(bot))