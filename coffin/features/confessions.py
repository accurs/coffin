import discord
import re
import datetime 

from discord.ext import commands 
from hashlib import sha256

from structure import (
  Context,
  Coffin,
  COFFIN
)

def confessions_enabled():
  async def predicate(interaction: discord.Interaction):
    channel = interaction.guild.get_channel(
      await interaction.client.db.fetchval(
        "SELECT channel_id FROM confessions.settings WHERE guild_id = $1", 
        interaction.guild.id
      )
    )
    if not channel:
      await interaction.alert("No confessions channel found!")
      return False

    return channel is not None
  return discord.app_commands.check(predicate)

def can_confess():
  async def predicate(interaction: discord.Interaction):
    result = await interaction.client.db.fetchrow(
      """
      SELECT * FROM confessions.muted
      WHERE guild_id = $1 
      AND hashed_member = $2
      """,
      interaction.guild.id, 
      sha256(bytes(str(interaction.user.id), "utf-8")).hexdigest()
    )

    if result:
      await interaction.response.send_message("You are muted from sending confessions in this server!")
      return False
    return True
  return discord.app_commands.check(predicate)

class ConfessionsModal(discord.ui.Modal, title="Send an annonymous confession"):
  confession = discord.ui.TextInput(
    label="What's on your mind?",
    style=discord.TextStyle.long,
    placeholder="Your super crazy secret confession...",
    max_length=2000
  )

  async def on_submit(self, interaction: discord.Interaction):
    result = await interaction.client.db.fetchrow(
      "SELECT * FROM confessions.settings WHERE guild_id = $1",
      interaction.guild.id
    )

    if not result: 
      raise Exception("Confessions feature was disabled while you were typing all that...")
    
    if not result.link_allowed:
      if re.search(
        r"(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])",
        self.confession.value
      ):
        return await interaction.alert("This server doesn't allow links in confessions")
    
    if not (channel := interaction.guild.get_channel(result.channel_id)):
      return await interaction.alert("The confession channel wasn't found")
    
    number = await interaction.client.db.fetchval(
      """
      SELECT COUNT(*) FROM confessions.confess
      WHERE guild_id = $1
      """,
      interaction.guild.id
    ) + 1

    embed = (
      discord.Embed(
        color=interaction.client.color, 
        description=self.confession.value,
        timestamp=datetime.datetime.now()
      )
      .set_author(
        name=f"annonymous confession #{number}",
        icon_url=interaction.guild.icon,
        url=COFFIN.SUPPORT_URL,
      )
      .set_footer(
        text="Wanna send annonymous confessions? Use the /confess command"
      )
    )

    await interaction.client.db.execute(
      """
      INSERT INTO confessions.confess
      VALUES ($1,$2) 
      """,
      interaction.guild.id,
      sha256(bytes(str(interaction.user.id), "utf-8")).hexdigest()
    )

    await channel.send(embed=embed)
    if (logs := interaction.guild.get_channel(result.logs)):
      embed = (
        discord.Embed(
          color=interaction.client.color,
          title=f"Anonymous confession #{number}",
          description=self.confession.value
        )
        .add_field(
          name="Made by",
          value=f"||{interaction.user.name} (`{interaction.user.id}`)||",
          inline=True
        )
      )
      await logs.send(embed=embed)
    return await interaction.response.send_message(f"Sent your confession in {channel.mention} {'\n**Notice:** Your confessions has been logged with ur user info in a private channel for moderation purposes' if logs else ''}", ephemeral=True)

class Confessions(commands.Cog):
  """
  Anonymous messages who was it
  """
  def __init__(self, bot: Coffin):
    self.bot = bot 
  
  @discord.app_commands.command()
  @confessions_enabled()
  @can_confess()
  async def confess(self, interaction: discord.Interaction):
    """
    Send an annonymous confession
    """
    return await interaction.response.send_modal(ConfessionsModal())

  @commands.hybrid_group(invoke_without_command=True)
  async def confessions(self, ctx: Context):
    """
    Manage annonymous confessions
    """
    return await ctx.send_help(ctx.command)

  @confessions.command(name="channel")
  @commands.has_permissions(manage_guild=True)
  async def confessions_channel(
    self, 
    ctx: Context, 
    *, 
    channel: discord.TextChannel
  ):
    """
    Assign a channel as a confessions channel
    """
    await self.bot.db.execute(
      """
      INSERT INTO confessions.settings
      (guild_id, channel_id) VALUES ($1,$2)  
      ON CONFLICT (guild_id) DO UPDATE
      SET channel_id = $2
      """,
      ctx.guild.id, channel.id
    )

    return await ctx.confirm(f"All the annonymous confessions will be sent to {channel.mention}\nTo confess use `/confess`")

  @confessions.command(name="logs")
  @commands.has_permissions(manage_guild=True)
  @commands.is_donator()
  async def confessions_logs(
    self, 
    ctx: Context,
    *,
    channel: discord.TextChannel = None
  ):
    """
    Assign a channel as a confessions logs channel (donator only)
    """
    await self.bot.db.execute(
      """
      INSERT INTO confessions.settings
      (guild_id, logs) VALUES ($1,$2)  
      ON CONFLICT (guild_id) DO UPDATE
      SET logs = $2
      """,
      ctx.guild.id, channel.id
    )
    return await ctx.confirm(f"Confessions logs channel set to {channel.mention}")

  @confessions.command(name="disable", aliases=['dis', 'd'])
  @confessions_enabled()
  @commands.has_permissions(manage_guild=True)
  async def confessions_disable(
    self,
    ctx: Context
  ):
    """
    Disable the confessions module
    """
    async def yes(interaction: discord.Interaction):
      await interaction.client.db.execute(
        "DELETE FROM confessions.settings WHERE guild_id = $1", 
        interaction.guild.id
      )

      await interaction.client.db.execute(
        "DELETE FROM confessions.confess WHERE guild_id = $1", 
        interaction.guild.id
      )

      await interaction.client.db.execute(
        "DELETE FROM confessions.muted WHERE guild_id = $1", 
        interaction.guild.id
      )

      embed = interaction.message.embeds[0]
      embed.description = "Succesfully disabled the confessions feature"
      return await interaction.response.edit_message(embed=embed, view=None)
    
    return await ctx.confirmation(
      "Are you sure you want to disable the confessions module? Every data related to this feature will be deleted",
      yes
    )
  
  @confessions.command(name="allowlinks")
  @confessions_enabled()
  @commands.has_permissions(manage_guild=True)
  async def confessions_allowlinks(
    self,
    ctx: Context,
    *,
    statement: bool
  ):
    """
    Allow use of links in confessions or not
    """
    await self.bot.db.execute(
      """
      UPDATE confessions.settings SET 
      link_allowed = $1 WHERE guild_id = $2 
      """,
      statement, ctx.guild.id
    )

    return await ctx.confirm(f"{'Enabled' if statement else 'Disabled'} the link usage in the future confessions!")

  @confessions.command(name="mute", example="4 use of slurs")
  @commands.has_permissions(moderate_members=True)
  async def confessions_mute(
    self, 
    ctx: Context, 
    number: int,
    *,
    reason: str = "No reason"
  ):
    """
    Mute the author of a confession
    """
    if number < 1: 
      return await ctx.alert("This confession number is not valid")

    hashed_member = await self.bot.db.fetchval(
      """
      SELECT hashed_member FROM confessions.confess
      WHERE guild_id = $1 OFFSET $2
      """,
      ctx.guild.id, number
    )

    if not hashed_member:
      return await ctx.alert("No member found for this confession")
    
    r = await self.bot.db.execute(
      """
      INSERT INTO confessions.muted 
      VALUES ($1,$2,$3,$4)
      ON CONFLICT (guild_id, hashed_member)
      DO NOTHING
      """,
      ctx.guild.id, hashed_member,
      number, reason
    )
    if r == "INSERT 0":
      return await ctx.alert("The author of this confession is already muted")

    return await ctx.confirm(f"Muted the author of confession **#{number}**")
  
  @confessions.command(name="unmute")
  @commands.has_permissions(manage_guild=True)
  async def confessions_unmute(
    self,
    ctx: Context,
    number: int
  ):
    """
    Unmute an author of a specific confession
    """
    r = await self.bot.db.execute(
      """
      DELETE FROM confessions.muted
      WHERE guild_id = $1 
      AND count = $2  
      """,
      ctx.guild.id, number
    )
    if r == "DELETE 0":
      return await ctx.alert("The author of this confession is not muted")
    
    return await ctx.confirm(f"Muted the author of confession **#{number}**")
  
  @confessions.command(name="muted")
  async def confessions_muted(
    self,
    ctx: Context
  ):
    """
    Get a list of all muted confessions
    """
    muted = await self.bot.db.fetch(
      """
      SELECT * FROM confessions.muted 
      WHERE guild_id = $1 
      ORDER BY number ASC
      """,
      ctx.guild.id
    )
    if not muted:
      return await ctx.alert("There's no muted confession")
    
    return await ctx.paginate(
      [
        f"**#{result.number}** - {result.reason}"
        for result in muted
      ],
      discord.Embed(title="Muted confession authors")
    )

async def setup(bot: Coffin) -> None:
  return await bot.add_cog(Confessions(bot))