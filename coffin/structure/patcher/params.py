from typing import Union
from discord.ext.commands import parameter 
from discord.ext.commands.errors import NoPrivateMessage
from discord import TextChannel, Thread
from structure.managers import Context

def default_role(ctx: Context):
  if guild := ctx.guild:
    return guild.default_role 
  
  raise NoPrivateMessage()

DefaultRole = parameter(
  default=default_role, 
  displayed_default="<everyone role>",
  converter=Union[TextChannel, Thread]
)
DefaultRole._fallback = True