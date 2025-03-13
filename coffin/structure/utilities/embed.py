import discord
import re
import datetime

from contextlib import suppress
from discord.ext import commands
from munch import Munch
from pydantic import BaseModel

from typing import (
  Any,
  Optional,
  Union
)
from structure.managers import Context

class User(BaseModel):
  mention: str
  id: int
  name: str
  discriminator: str
  created_at: Any
  joined_at: Any
  avatar: str
  global_name: str

  def __str__(self):
    return (
      self.name
      if self.discriminator != "0"
      else f"{self.name}#{self.discriminator}"
    )

class Guild(BaseModel):
  name: str
  id: int
  icon: Optional[str]
  banner: Optional[str]
  created_at: Any
  owner: User
  member_count: int
  description: Optional[str]
  boost_level: int
  boosts: int
  vanity_code: Optional[str]
  shard: int
  preferred_locale: Optional[str]

  def __str__(self):
    return self.name

class Moderator(User):
  command: str

class Script(commands.Converter):
  async def convert(self, ctx: Context, argument: str):
    x = await ctx.bot.embed.convert(ctx.author, argument)
    return x

class Embed:
  def init_models(self: "Embed", member: Union[discord.Member, discord.User]):
    user = User(
      mention=member.mention,
      id=member.id,
      name=member.name,
      discriminator=member.discriminator,
      created_at=member.created_at,
      joined_at=getattr(member, "joined_at", None),
      avatar=member.display_avatar.url,
      global_name=member.global_name or member.name,
    )
    kwargs = {'user': user}

    if isinstance(member, discord.Member):
      o = member.guild.owner  
      
      owner = User(
        mention=o.mention,
        id=o.id,
        name=o.name,
        discriminator=o.discriminator,
        created_at=o.created_at,
        joined_at=o.joined_at,
        avatar=o.display_avatar.url,
        global_name=o.global_name or o.name,
      )
  
      guild = Guild(
        name=member.guild.name,
        id=member.guild.id,
        icon=str(member.guild.icon),
        banner=str(member.guild.banner),
        created_at=member.guild.created_at,
        owner=owner,
        member_count=member.guild.member_count,
        description=member.guild.description,
        boosts=member.guild.premium_subscription_count,
        boost_level=member.guild.premium_tier,
        vanity_code=member.guild.vanity_url_code,
        shard=member.guild.shard_id,
        preferred_locale=str(member.guild.preferred_locale),
      )
      kwargs['guild'] = guild

    return kwargs

  def get_params(self, text: str) -> Union[tuple, str]:
    return re.findall(r"\{([^{}]+?):\s*((?:[^{}]|(?:\{[^{}]*?\}))+)\}", text) or text

  def find(self, array: list, index: int) -> Optional[Any]:
    try:
      return array[index]
    except IndexError:
      return ""

  async def convert(
    self,
    member: Union[discord.Member, discord.User],
    text: str,
    new_models: Optional[dict] = None,
  ) -> dict:
    models = self.init_models(member)
    if new_models:
      models.update(new_models)

    content: Optional[str] = None
    embed: Optional[discord.Embed] = None
    delete_after: Optional[int] = None
    view = discord.ui.View()
    dict_embed = {"fields": []}

    params = self.get_params(text)

    if isinstance(params, str):
      return {"content": params.format(**Munch(**models))}

    for key, value in params:
      match key:
        case "title":
          dict_embed["title"] = value.format(**Munch(**models))
        case "description":
          dict_embed["description"] = value.format(**Munch(**models))
        case "thumbnail":
          dict_embed["thumbnail"] = {"url": value.format(**Munch(**models))}
        case "image":
          dict_embed["image"] = {"url": value.format(**Munch(**models))}
        case "timestamp":
          match value:
            case "now":
              dict_embed["timestamp"] = (
                  datetime.datetime.now().isoformat()
              )
            case "joined_at":
              dict_embed["timestamp"] = member.joined_at.isoformat()
            case "created_at":
              dict_embed["timestamp"] = member.created_at.isoformat()
        case "color":
          try:
            dict_embed["color"] = int(value[1:], 16)
          except ValueError:
            dict_embed["color"] = int("2f3136", 16)
        case "content":
          content = value.format(**Munch(**models))
        case "author":
          values = value.split(" && ")
          dict_embed["author"] = {
            "name": values[0].format(**Munch(**models)),
            "icon_url": self.find(values, 1).format(**Munch(**models)),
            "url": self.find(values, 2).format(**Munch(**models)),
          }
        case "footer":
          values = value.split(" && ")
          dict_embed["footer"] = {
            "text": values[0].format(**Munch(**models)),
            "icon_url": self.find(values, 1).format(**Munch(**models)),
          }
        case "field":
          values = value.split(" && ")
          with suppress(IndexError):
            dict_embed["fields"].append(
              {
                "name": values[0].format(**Munch(**models)),
                "value": values[1].format(**Munch(**models)),
                "inline": str(self.find(values, 2)).lower() == "true",
              }
              )
        case "delete":
          with suppress(ValueError):
            delete_after = int(value)
        case "button":
          with suppress(Exception):
            values = value.split(" && ")
            label = values[0].format(**Munch(**models))
            obj = self.find(values, 1).format(**Munch(**models))
            obj2 = self.find(values, 2).format(**Munch(**models))
            
            url = None 
            emoji = None

            url_regex = re.compile(r"(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])")
            
            if obj:
              if url_regex.match(obj):
                url = obj
              else:
                emoji = discord.PartialEmoji.from_str(obj)

            if obj2: 
              if url_regex.match(obj2):
                url = obj2
              else:
                emoji = discord.PartialEmoji.from_str(obj2) 

            view.add_item(
              discord.ui.Button(
                label=label,
                url=url,
                disabled=not url,
                emoji=emoji
              )
            )
        case _:
            continue

    if len(dict_embed.keys()) > 1:
      embed = discord.Embed.from_dict(dict_embed)

    return {
      "content": content,
      "embed": embed,
      "view": view,
      "delete_after": delete_after,
    }