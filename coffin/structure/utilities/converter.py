import argparse
import asyncio
import datetime
import json
import html
import re
import aiohttp

from contextlib import suppress
from bs4 import BeautifulSoup
from humanfriendly import parse_timespan
from pytz import timezone
from timezonefinder import TimezoneFinder

from discord import (
  Colour,
  Member as DefaultMember,
  PartialEmoji,
  Role
)
from discord.ext.commands import (
  BadArgument,
  ColorConverter,
  Converter,
  MemberConverter,
  RoleConverter,
  RoleNotFound,
  TextChannelConverter,
)
from .models import (
  CashAppProfile,
  Error,
  RobloxUser,
  SnapchatUser,
  TikTokUser,
  WeatherCondition,
  WeatherFeelsLike,
  WeatherModel,
  WeatherTemperature,
  WeatherWind,
  TelegramUser,
  PinterestUser,
  SnapchatCelebrity,
  SnapStory,
  ThreadsUser,
  InstagramUser,
  Images,
  TwitterUser
)
from typing import (
  Dict,
  Optional
)
from structure.managers import Context, getLogger

logger = getLogger(__name__)

class Twitter(Converter):
  async def convert(self: "Twitter", ctx: Context, argument: str) -> TwitterUser:
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
      "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
      "X-Csrf-Token": "f6ee16e05efd00d28478de3eb9da3ce7ffb857d81b025bdbf6541cb8af1ddae41d43760fd8393f4370325392b88ffc4e61dfada5e0006df615f21644d2c676ce4b94d72970953c15ca0d4196d6997c3c",
      "X-Client-Uuid": "bf9a7732-e196-46a8-a11c-50aa7010dace",
      "X-Twitter-Auth-Type": "OAuth2Session",
      "Cookie": "auth_token=be72ba764a0919bfb3c3221492894a7856c76e6d;ct0=f6ee16e05efd00d28478de3eb9da3ce7ffb857d81b025bdbf6541cb8af1ddae41d43760fd8393f4370325392b88ffc4e61dfada5e0006df615f21644d2c676ce4b94d72970953c15ca0d4196d6997c3c",
    }
    params = {
      "variables": json.dumps(
        {
          "screen_name": argument,
          "withSafetyModeUserFields": True,
        }
      ),
      "features": json.dumps(
        {
          "hidden_profile_subscriptions_enabled": True,
          "rweb_tipjar_consumption_enabled": True,
          "responsive_web_graphql_exclude_directive_enabled": True,
          "verified_phone_label_enabled": False,
          "subscriptions_verification_info_is_identity_verified_enabled": True,
          "subscriptions_verification_info_verified_since_enabled": True,
          "highlights_tweets_tab_ui_enabled": True,
          "responsive_web_twitter_article_notes_tab_enabled": True,
          "subscriptions_feature_can_gift_premium": True,
          "creator_subscriptions_tweet_preview_api_enabled": True,
          "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
          "responsive_web_graphql_timeline_navigation_enabled": True,
        }
      ),
      "fieldToggles": json.dumps(
        {
          "withAuxiliaryUserLabels": False,
        }
      )
    }

    data = await ctx.bot.session.get(
      "https://x.com/i/api/graphql/Yka-W8dz7RaEuQNkroPkYw/UserByScreenName",
      headers=self.headers,
      params=params
    )
    if not data['data']:
      return Error(f"Twitter user `{argument}` not found")
    
    user = data['data']['user']['result']['legacy']
    stat = data['data']['user']['result']

    return TwitterUser(
      username=argument,
      id=stat['rest_id'],
      avatar=user['profile_image_url_https'],
      bio=user['description'],
      display_name=user['name'],
      location=user['location'],
      verified=stat['is_blue_verified'],
      created_at=user['created_at'],
      followers=user['followers_count'],
      following=user['friends_count'],
      posts=user['media_count'],
      liked_posts=user['favourites_count'],
      tweets=user['statuses_count'],
      url=f"https://x.com/@{argument}"
    )

class Instagram(Converter):
  async def convert(self: "Instagram", ctx: Context, argument: str) -> InstagramUser:
    self.headers = {
      "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 105.0.0.11.118 (iPhone11,8; iOS 12_3_1; en_US; en-US; scale=2.00; 828x1792; 165586599)",
      "Cookie": "csrftoken=0caLAnUqwOarLMVvbjXAS27Gy3gi1vrg; sessionid=62611218321%3A8UrKhzCCdJYO9h%3A2%3AAYeYP7_bYxI73GzZywBL9KDlEfRjGLj7XanKP8s5HQ",
    }

    r = await ctx.bot.session.get(
      "https://www.instagram.com/api/v1/users/web_profile_info",
      params={"username": argument},
      headers=self.headers
    )
    if not r["data"]["user"]:
      raise Error(f"Instagram user `{argument}` not found")
    
    user = r["data"]["user"]
    return InstagramUser(
      username=argument,
      full_name=user['full_name'],
      bio=user['biography'],
      is_private=user['is_private'],
      is_verified=user['is_verified'],
      id=user['id'],
      followers=user['edge_followed_by']['count'],
      following=user['edge_follow']['count'],
      posts=user['edge_owner_to_timeline_media']['count'],
      pronouns=user['pronouns'],
      avatar_url=user['profile_pic_url_hd'],
      biolinks={link["title"]: link["url"] for link in user["bio_links"]},
      url=f"https://instagram.com/{argument}"
    )

class Brave(Converter):
  async def convert(self, ctx: Context, argument: str) -> Images:
    html = await ctx.bot.session.get(f"https://search.brave.com/images", params={"q": argument, "safesearch": "strict"})
    imgs = re.findall(r'<img[^>]+src="([^">]+)"', html)
    r = list(filter(lambda img: re.match(r"^https://imgs.search.brave.com/", img) and '32:32' not in img, imgs))
    if not r:
      raise Error("No images found")

    return Images(
      query=argument,
      images=r
    )

class RobloxTool:
  def __init__(self):
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"
    }
    self.session = aiohttp.ClientSession(
      headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)
    )

  async def get_user_id(self, username: str) -> Optional[str]:
    """
    Get the roblox user id by username
    """
    params = {"username": username}
    r = await self.session.get("https://www.roblox.com/users/profile", params=params)
    if r.ok:
      return str(r.url)[len("https://www.roblox.com/users/") :].split("/")[0]

    return None

  async def get_user_stats(self, user_id: str) -> Dict[str, int]:
    payload = {}

    for statistic in ["friends", "followers", "followings"]:
      r = await self.session.get(f"https://friends.roblox.com/v1/users/{user_id}/{statistic}/count")
      if r.status == 200:
        data = await r.json()
        payload.update({statistic: data["count"]})
      else:
        payload.update({statistic: 0})

    return payload

  async def get_user_avatar(self, user_id: str):
    """
    Get the user's avatar
    """
    r = await self.session.get(f"https://www.roblox.com/users/{user_id}/profile")
    html = await r.text()
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("meta", property="og:image")["content"]

  async def get_user_profile(self, user_id: str) -> dict:
    """
    Get the user's profile by id
    """
    r = await self.session.get(f"https://users.roblox.com/v1/users/{user_id}")
    return await r.json()

  async def scrape(self, username: str) -> dict:
    """
    Get details about a roblox profile by username
    """
    if user_id := await self.get_user_id(username):
      profile_data = await self.get_user_profile(user_id)
      profile_stats = await self.get_user_stats(user_id)
      user_avatar = await self.get_user_avatar(user_id)
      await self.session.close()
      return {
        "username": profile_data["name"],
        "display_name": profile_data["displayName"],
        "bio": profile_data["description"],
        "id": user_id,
        "created_at": datetime.datetime.strptime(
          profile_data["created"].split(".")[0] + "Z", "%Y-%m-%dT%H:%M:%SZ"
        ),
        "banned": profile_data["isBanned"],
        "avatar_url": user_avatar,
        "url": f"https://www.roblox.com/users/{user_id}/profile",
        **profile_stats,
      }

    return None

class Roblox(Converter):
  def __init__(self):
    self.roblox = RobloxTool()
    super().__init__()

  async def convert(self, ctx: Context, argument: str) -> RobloxUser:
    result = await self.roblox.scrape(argument)
    if not result:
      raise Error(f"Roblox user `{argument}` not found")

    return RobloxUser(**result)

class Snapchat(Converter):
  async def convert(self, ctx: Context, argument: str) -> SnapchatUser:
    html = await ctx.bot.session.get(f"https://www.snapchat.com/add/{argument}")
    soup = BeautifulSoup(html, "html.parser")
    h = soup.find("h5")

    if not (pfp := soup.find("img", alt="Profile Picture")):
      images = soup.find_all("img")
      bitmoji = images[0]["srcset"]
      snapcode = images[-1]["src"].replace("SVG", "PNG")
    else:
      bitmoji = pfp['srcset']
      snapcode = None

    display = soup.find(
      "span",
      attrs={
        "class": "PublicProfileDetailsCard_displayNameText__naDQ0 PublicProfileDetailsCard_textColor__HkkEs PublicProfileDetailsCard_oneLineTruncation__VOhsx"
      },
    ) or soup.find("h4")
    user = h.find("span") or h

    return SnapchatUser(
      display_name=display.text,
      username=user.text,
      bitmoji=bitmoji,
      snapcode=snapcode,
    )

class SnapchatStory(Converter):
  async def convert(self, ctx: Context, argument: str) -> SnapchatCelebrity:
    user = await Snapchat().convert(ctx, argument)
    html = await ctx.bot.session.get(f"https://www.snapchat.com/add/{argument}")
    SCRIPT = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')

    if not (matching := SCRIPT.search(html)):
      raise BadArgument("Couldn't fetch the stories for some reason")
    
    res = json.loads(matching.group(1))
    if not (feed := res['props']['pageProps'].get('story')):
      raise BadArgument(f"**@{user.username}** has **no** stories")
    
    stories = feed['snapList']

    return SnapchatCelebrity(
      **dict(user),
      stories=[
        SnapStory(
          index=story['snapIndex'],
          media_type=story['snapMediaType'],
          media_url=story['snapUrls']['mediaUrl'],
          timestamp=story['timestampInSec']['value']
        )
        for story in stories
      ]
    )

class Tiktok(Converter):
  async def convert(self, ctx: Context, argument: str):
    result = await ctx.bot.session.get(f"https://tiktok.com/@{argument}")
    soup = BeautifulSoup(result, "html.parser")
    script = soup.find("script", id="__UNIVERSAL_DATA_FOR_REHYDRATION__")
    x = json.loads(script.text)["__DEFAULT_SCOPE__"]["webapp.user-detail"]

    if x["statusCode"] == 10221:
      raise Error(f"Tiktok User `@{argument}` not found")

    payload = {
      "username": x["userInfo"]["user"]["uniqueId"],
      "nickname": x["userInfo"]["user"]["nickname"],
      "avatar": x["userInfo"]["user"]["avatarMedium"],
      "bio": x["userInfo"]["user"]["signature"],
      "verified": x["userInfo"]["user"]["verified"],
      "private": x["userInfo"]["user"]["privateAccount"],
      "followers": x["userInfo"]["stats"]["followerCount"],
      "following": x["userInfo"]["stats"]["followingCount"],
      "hearts": x["userInfo"]["stats"]["heart"],
      "url": f"https://tiktok.com/@{x['userInfo']['user']['uniqueId']}",
    }

    return TikTokUser(**payload)

class CashApp(Converter):
  async def convert(self, ctx: Context, argument: str):
    html = await ctx.bot.session.get(f"https://cash.app/{argument}")
    soup = BeautifulSoup(html, "html.parser")
    qr = "https://cash.app" + soup.find("img")["src"]
    info = json.loads(re.search("var profile = ([^;]*)", soup.prettify()).group(1))
    payload = {
      "display_name": info["display_name"],
      "tag": info["formatted_cashtag"],
      "avatar_url": info["avatar"]["image_url"],
      "accent_color": info["avatar"]["accent_color"],
      "qr_url": qr,
    }
    return CashAppProfile(**payload)

class Pinterest(Converter):
  async def convert(self, ctx: Context, argument: str) -> PinterestUser:
    url = f"https://ro.pinterest.com/resource/UserResource/get/?source_url=%2F{argument}%2F&data=%7B%22options%22%3A%7B%22username%22%3A%22{argument}%22%7D%2C%22context%22%3A%7B%7D%7D&_=1729785118099"
    
    try:
      response = await ctx.bot.session.get(url)
    except aiohttp.ClientResponseError:
      raise BadArgument(f"Pinterest user **{argument}** not found")
    
    data = response['resource_response']['data']
    
    return PinterestUser(
      username=data['username'],
      full_name=data['full_name'],
      website_url=data['website_url'],
      about=data['about'],
      pronouns=data['pronouns'],
      followers=data['follower_count'],
      following=data['explicit_user_following_count'],
      boards=data['board_count'],
      profile_picture_url=data['image_xlarge_url']
    )

class Telegram(Converter):
  async def convert(self, ctx: Context, argument: str) -> TelegramUser:
    html = await ctx.bot.session.get(f"https://t.me/{argument}")

    DISPLAY_NAME = re.compile(r'<span dir="auto">(.*?)</span>')
    BIO = re.compile(r'<div class="tgme_page_description ">(.*?)</div>')
    PROFILE_PIC = re.compile(r'<img class="tgme_page_photo_image" src="(.*?)">')
    
    if not (username_match := DISPLAY_NAME.search(html)):
      raise BadArgument(f"**@{argument}** is **not** a valid Telegram username")

    user = {
      "username": argument,
      "display_name": username_match.group(1),
      "bio": BIO.search(html).group(1) if BIO.search(html) else None,
      "profile_pic": PROFILE_PIC.search(html).group(1) if PROFILE_PIC.search(html) else None
    }

    return TelegramUser(**user)

class Threads(Converter):
  async def convert(self, ctx: Context, argument: str):
    payload = await ctx.bot.session.get(f"https://www.threads.net/@{argument}", )

    biography = re.compile(r"""<meta\s+property=["']og:description["']\s+content=["']([^"']+)["']""")
    image = re.compile(r"""<meta\s+property=["']og:image["']\s+content=["']([^"']+)["']""")
    title_pattern = re.compile(r"""<meta\s+property=["']og:title["']\s+content=["']([^"']+)["']""")

    if not (bio_search := biography.search(payload)):
      raise BadArgument(f"**@{argument}** is **not** a valid **Threads** user")
    
    return ThreadsUser(
      bio=html.unescape(bio_search.group(1)),
      profile_pic=html.unescape(image.search(payload).group(1)),
      title=html.unescape(re.sub(r'\son\sThreads', "", title_pattern.search(payload).group(1))),
      url=f"https://www.threads.net/@{argument}"
    )

class Weather(Converter):
  async def convert(self, ctx: Context, argument: str) -> WeatherModel:
    x = await ctx.bot.session.get(
      "https://api.weatherapi.com/v1/current.json",
      params={"q": argument, "key": ctx.bot.weather},
  )

    return WeatherModel(
      city=x["location"]["name"],
      country=x["location"]["country"],
      last_updated=datetime.datetime.fromtimestamp(
        x["current"]["last_updated_epoch"]
      ),
      localtime=datetime.datetime.now(tz=timezone(x["location"]["tz_id"])),
      temperature=WeatherTemperature(
        celsius=x["current"]["temp_c"], fahrenheit=x["current"]["temp_f"]
      ),
      feelslike=WeatherFeelsLike(
        celsius=x["current"]["feelslike_c"],
        fahrenheit=x["current"]["feelslike_f"],
      ),
      wind=WeatherWind(
        mph=x["current"]["wind_mph"], kph=x["current"]["wind_kph"]
      ),
      condition=WeatherCondition(
        text=x["current"]["condition"]["text"],
        icon=f"http:{x['current']['condition']['icon']}",
      ),
      humidity=x["current"]["humidity"],
    )

class Bank(Converter):
  async def convert(self: "Bank", ctx: Context, argument: str):
    if not argument.isdigit() and argument.lower() != "all":
      raise BadArgument("This is not a number")

    bank = await ctx.bot.db.fetchval("SELECT bank FROM economy WHERE user_id = $1", ctx.author.id)
    points = bank if argument.lower() == "all" else int(argument)

    if points == 0:
      raise BadArgument("The value cannot be 0")

    if points > bank:
      raise BadArgument(
        f"You do not have `{int(argument):,}` credits in your bank"
      )

    return points

class GiveawayCreate(Converter):
  def __init__(self):
    self.parser = argparse.ArgumentParser(description="Giveaway")
    self.parser.add_argument("reward", nargs="+")
    self.parser.add_argument("--time", "-t", default="1h", required=False)
    self.parser.add_argument(
      "--winners", "-w", default=1, type=int, required=False, choices=range(1, 6)
    )

  async def convert(
    self: "GiveawayCreate", ctx: Context, argument: str
  ) -> argparse.Namespace:
    try:
      args = self.parser.parse_args(argument.split())
    except SystemExit:
      raise BadArgument("Arguments were given incorrectly")
    except Exception as e:
      logger.warning(f"Error for giveaway - {e}")

    args.reward = " ".join(args.reward)
    return args

class TwitchStreamer(Converter):
  async def convert(self: "TwitchStreamer", ctx: Context, argument: str):
    r = await ctx.bot.session.get(
      f"https://twitch.tv/{argument}",
      headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0"
      }
    )
    if matching := re.search(
      r'<meta name="twitter:app:url:googleplay" content="twitch.tv/([\S]+)"/>', 
      r
    ):
      return matching.group(1)
    
    else:
      raise BadArgument("Twitch streamer not found")

class YouTuber(Converter):
  async def convert(self: "YouTuber", ctx: Context, argument: str):
    try:
      await ctx.bot.session.get(
        f"https://youtube.com/@{argument}",
        headers={
          "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
        },
      )
      return argument
    except Exception:
      raise BadArgument("This youtuber was not found")

class Channel(TextChannelConverter):
  async def convert(self, ctx: Context, argument: str):
    if argument == "all":
      return argument

    return await super().convert(ctx, argument)

class Value(Converter):
  async def convert(self: "Value", ctx: Context, argument: str):
    if not argument.isdigit() and argument.lower() != "all" and not argument.lower().endswith(("k", "%")):
      raise BadArgument("This is not a number")

    credits = await ctx.bot.db.fetchval("SELECT credits FROM economy WHERE user_id = $1", ctx.author.id)
    if argument.lower() == "all":
      points = credits
    
    elif argument.lower().endswith("k"):
      points = int(argument[:-1]) * 1000
    
    elif argument.lower().endswith("%"):
      points = (credits * int(argument[:-1])) // 100
    
    else:
      points = int(argument)

    if points == 0:
      raise BadArgument("The value cannot be 0")

    if points > credits:
      raise BadArgument(f"You do not have `{int(argument):,}` credits")

    return points

class ValidPermission(Converter):
  async def convert(self: "ValidPermission", ctx: Context, argument: str):
    perms = [
      p
      for p in dir(ctx.author.guild_permissions)
      if isinstance(getattr(ctx.author.guild_permissions, p), bool)
    ]

    if argument not in perms:
      raise BadArgument("This is **not** a valid permission")

    return argument

class ValidAlias(Converter):
  async def convert(self: "ValidAlias", ctx: Context, argument: str):
    all_aliases = ctx.bot.flatten(
      [
        list(map(lambda cm: cm.lower(), c.aliases))
        for c in set(ctx.bot.walk_commands())
        if c.aliases
      ]
    )
    if argument.lower() in all_aliases:
      raise BadArgument("This is **already** an existing alias for a command")

    return argument

class Time(Converter):
  async def convert(self, ctx: Context, argument: str):
    try:
      return parse_timespan(argument)
    except Exception:
      raise BadArgument("This is not a valid timestamp")

class ValidCommand(Converter):
  async def convert(self: "ValidCommand", ctx: Context, argument: str):
    if not ctx.bot.get_command(argument) or getattr(
      ctx.bot.get_command(argument), "cog_name", ""
    ).lower() in ["developer", "jishaku"]:
      raise BadArgument("This is **not** a valid command")

    return ctx.bot.get_command(argument).qualified_name

class AssignableRole(RoleConverter):
  async def convert(self, ctx: Context, argument: str) -> Role:
    try:
      role = await super().convert(ctx, argument)
    except RoleNotFound:
      role = ctx.find_role(argument)
      if not role:
        raise RoleNotFound(argument)
    finally:
      if not role or not role.is_assignable():
        raise Error("This role cannot be assigned by me")

      if ctx.author.id != ctx.guild.owner_id:
        if role >= ctx.author.top_role:
          raise Error("You cannot manage this role")

      return role

class Location(Converter):
  async def convert(self, ctx: Context, argument: str):
    params = {"q": argument, "format": "json"}

    result = await ctx.bot.session.get("https://nominatim.openstreetmap.org/search", params=params)
    if not result:
      raise BadArgument("This location was not found")

    kwargs = {"lat": float(result[0]["lat"]), "lng": float(result[0]["lon"])}

    return await asyncio.to_thread(TimezoneFinder().timezone_at, **kwargs)

class DiscordEmoji(Converter):
  async def convert(self, ctx: Context, argument: str):
    custom_regex = re.compile(r"(<a?)?:\w+:(\d{18}>)?")
    unicode_regex = re.compile(
      r"["
      "\U0001F1E0-\U0001F1FF"
      "\U0001F300-\U0001F5FF"
      "\U0001F600-\U0001F64F"
      "\U0001F680-\U0001F6FF"
      "\U0001F700-\U0001F77F"
      "\U0001F780-\U0001F7FF"
      "\U0001F800-\U0001F8FF"
      "\U0001F900-\U0001F9FF"
      "\U0001FA00-\U0001FA6F"
      "\U0001FA70-\U0001FAFF"
      "\U00002702-\U000027B0"
      "\U000024C2-\U0001F251"
      "]+"
    )

    if not custom_regex.match(argument) and not unicode_regex.match(argument):
      raise BadArgument("This is not an emoji")

    return PartialEmoji.from_str(argument)

class ImageData:
  async def convert(self, ctx: Context, argument: str) -> bytes:
    pinterest = re.compile(
      r"https://i.pinimg.com/564x/([^/]{2})/([^/]{2})/([^/]{2})/([^.]*).jpg"
    )
    discord_cdn = re.compile(
      r"https://cdn.discordapp.com/attachments/([^/][0-9]+)/([^/][0-9]+)/([^.]*).(jpg|png|gif)(.*)"
    )
    catbox = re.compile(r"https://files.catbox.moe/([^.]*).(jpg|png|gif)")
    if (
      not pinterest.match(argument)
      and not discord_cdn.match(argument)
      and not catbox.match(argument)
    ):
      raise BadArgument(
        "Bad URL was given. It must be a **pinterest**, **discord** or **catbox** image URL"
      )

    return await ctx.bot.session.get(argument)

class Color(ColorConverter):
  async def convert(self, ctx: Context, argument: str):
    try:
      return await super().convert(ctx, argument)
    except Exception:
      try:
        return getattr(Colour, "_".join(argument.split(" ")))()
      except Exception:
        raise Error("This color is not available")

class ChartSize(Converter):
  async def convert(self, ctx: Context, argument: str):
    if not re.match(r"[0-9]x[0-9]", argument):
      raise Error("Wrong size format. Example: 3x3")

    return argument

class ValidDate(Converter):
  async def convert(self, ctx: Context, argument: str):
    now = datetime.datetime.now()
    argument += f" {now.year}"
    formats = [
      "%d %B %Y",
      "%d %b %Y",
      "%B %d %Y",
      "%b %d %Y",
      "%d %m %y",
      "%m %d %y",
    ]

    date = None

    for form in formats:
      with suppress(ValueError):
        date = datetime.datetime.strptime(argument, form)
        break

    if not date:
      raise BadArgument("Date is not valid")

    if date < now:
      date = date.replace(year=date.year + 1)

    return date

class Member(MemberConverter):
  async def convert(self, ctx: Context, argument: str) -> DefaultMember:
    member = await super().convert(ctx, argument)

    if member.top_role >= ctx.me.top_role:
      raise Error(
        f"I am unable to invoke `{ctx.command.qualified_name}` on {member.mention}!"
      )

    elif ctx.author == ctx.guild.owner:
      return member

    elif member == ctx.guild.owner:
      raise Error(
        f"You are unable to invoke `{ctx.command.qualified_name}` on {member.mention}!"
      )

    elif member.top_role >= ctx.author.top_role:
      raise Error(
        f"You are unable to invoke `{ctx.command.qualified_name}` on {member.mention}!"
      )

    elif member == ctx.author:
      raise Error(
        f"You are unable to invoke `{ctx.command.qualified_name}` on yourself!"
      )

    return member

class Percentage(Converter):
  async def convert(self, ctx: Context, argument: str) -> int:
    if argument.isdigit():
      argument = int(argument)

    elif match := re.compile(r"(?P<percentage>\d+)%").match(argument):
      argument = int(match.group(1))

    else:
      argument = 0

    if argument < 0 or argument > 200:
      raise Error("Please provide a valid percentage!")

    return argument

class Position(Converter):
  async def convert(self, ctx: Context, argument: str) -> int:
    argument = argument.lower()
    player = ctx.voice_client
    ms: int = 0

    if ctx.invoked_with == "ff" and not argument.startswith("+"):
      argument = f"+{argument}"

    elif ctx.invoked_with == "rw" and not argument.startswith("-"):
      argument = f"-{argument}"

    if match := re.compile(
      r"(?P<h>\d{1,2}):(?P<m>\d{1,2}):(?P<s>\d{1,2})"
    ).fullmatch(argument):
      ms += (
          int(match.group("h")) * 3600000
          + int(match.group("m")) * 60000
          + int(match.group("s")) * 1000
      )

    elif match := re.compile(r"(?P<m>\d{1,2}):(?P<s>\d{1,2})").fullmatch(argument):
      ms += int(match.group("m")) * 60000 + int(match.group("s")) * 1000

    elif (
      match := re.compile(r"(?P<s>(?:\-|\+)\d+)\s*s").fullmatch(argument)
    ) and player:
      ms += player.position + int(match.group("s")) * 1000

    elif match := re.compile(r"(?:(?P<m>\d+)\s*m\s*)?(?P<s>\d+)\s*[sm]").fullmatch(
      argument
    ):
      if m := match.group("m"):
        if match.group("s") and argument.endswith("m"):
          return Error("Invalid position provided!")

        ms += int(m) * 60000

      elif s := match.group("s"):
        if argument.endswith("m"):
          ms += int(s) * 60000
        else:
          ms += int(s) * 1000

    else:
      return Error("Invalid position provided!")

    return ms
