import discord

from cachetools import TTLCache
from dataclasses import dataclass

@dataclass 
class UserTag:
  tag: str 
  badge_id: str 
  identity_guild_id: int 

  @classmethod  
  def from_dict(self, data: dict[str, int | str] | None):
    return self(
      tag=data.get("tag"),
      badge_id=data.get("badge"),
      identity_guild_id=data.get("identity_guild_id")
    ) if data else data
  
  @property
  def badge(self) -> str:
    return "https://cdn.discordapp.com/clan-badges/{identity_guild_id}/{badge_id}.png".format(identity_guild_id=self.identity_guild_id, badge_id=self.badge_id)

def is_dangerous(self: "discord.Member"):
  return any(
    [
      self.guild_permissions.administrator,
      self.guild_permissions.manage_channels,
      self.guild_permissions.manage_roles,
      self.guild_permissions.manage_expressions,
      self.guild_permissions.kick_members,
      self.guild_permissions.ban_members,
      self.guild_permissions.manage_webhooks,
      self.guild_permissions.manage_guild,
    ]
  )

discord.Member.is_dangerous = is_dangerous
discord.Member.is_punishable = (
  lambda self: self.id != self.guild.owner_id
  and self.top_role < self.guild.me.top_role
)
discord.User.url = discord.Member.url = property(
  fget=lambda self: f"https://discord.com/users/{self.id}", doc="The user's url"
)

cache = TTLCache(maxsize=100, ttl=3600)

async def fetch_tag(self: discord.User) -> UserTag | None:
  """
  Fetch the user's tag (if they have one)
  """
  if result := cache.get(self.id):
    return result 
  
  user = await self._state.http.get_user(self.id)
  cache[self.id] = UserTag.from_dict(user['clan'])
  return cache[self.id]

discord.User.fetch_tag = fetch_tag