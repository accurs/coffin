import discord
import random
import asyncio
import numexpr
import datetime
import textwrap

from io import BytesIO
from contextlib import suppress
from difflib import SequenceMatcher
from discord.ext import commands
from rembg import remove, new_session

from PIL import (
  Image, 
  ImageDraw, 
  ImageFont, 
  ImageFilter, 
  ImageOps
)
from asyncio import (
  create_task,
  all_tasks,
  gather,
  CancelledError
)
from structure import (
  Coffin,
  Context,
  ratelimiter
)
from typing import (
  Optional,
  List
)

session = new_session()

class BlackteaButton(discord.ui.Button):
  def __init__(self):
    self.users = []
    super().__init__(emoji="☕", label="(0)")

  async def callback(self, interaction: discord.Interaction):
    if interaction.user.id in self.users:
      self.users.remove(interaction.user.id)
    else:
      self.users.append(interaction.user.id)

    self.label = f"({len(self.users)})"
    return await interaction.response.edit_message(view=self.view)

class TicTacToeButton(discord.ui.Button):
  def __init__(self, x: int, y: int, label: str):
    self.x = x
    self.y = y
    super().__init__(label=label, row=self.x)

  async def callback(self, interaction: discord.Interaction):
    assert self.view is not None
    self.disabled = True

    match self.view.turn:
      case "X":
        self.style = discord.ButtonStyle.red
        self.label = self.view.turn
        self.view.turn = "O"
        self.view.player = self.view.player2
        self.view.board[self.x][self.y] = self.view.X
      case _:
        self.style = discord.ButtonStyle.green
        self.label = self.view.turn
        self.view.turn = "X"
        self.view.player = self.view.player1
        self.view.board[self.x][self.y] = self.view.O

    if winner := self.view.check_winner():
      self.view.stop()
      match winner:
        case self.view.X:
          return await interaction.response.edit_message(
            content=f"{self.view.player1.mention} Won the game!",
            view=self.view,
            allowed_mentions=discord.AllowedMentions.none(),
          )

        case self.view.O:
          return await interaction.response.edit_message(
            content=f"{self.view.player2.mention} Won the game!",
            view=self.view,
            allowed_mentions=discord.AllowedMentions.none(),
          )
        case _:
          return await interaction.response.edit_message(
            content="It's a tie", view=self.view
          )

    content = (
      f"It's {self.view.player1.mention}'s turn"
      if self.view.turn == "X"
      else f"It's {self.view.player2.mention}'s turn"
    )
    return await interaction.response.edit_message(
      content=content,
      view=self.view,
      allowed_mentions=discord.AllowedMentions.none(),
    )

class TicTacToe(discord.ui.View):
  def __init__(
    self,
    player1: discord.Member,
    player2: discord.Member,
  ):
    self.player1 = player1
    self.player2 = player2
    self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    self.turn = "X"
    self.player = player1
    self.X = 1
    self.O = -1
    self.tie = 2
    self.stopped = False
    super().__init__()

    for x in range(3):
      for y in range(3):
        self.add_item(TicTacToeButton(x, y, label="ㅤ"))

  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    if interaction.user.id != self.player.id:
      await interaction.response.send_message(
        "It's not your turn", ephemeral=True
      )

    return interaction.user.id == self.player.id

  def check_winner(self) -> Optional[int]:
    if any([sum(s) == 3 for s in self.board]):  # checking if X won on a line
      return self.X

    if any([sum(s) == -3 for s in self.board]):  # checking if O won on a line
      return self.O

    value = sum([self.board[i][i] for i in range(3)])  # checking diagonals
    if value == 3:
      return self.X
    elif value == -3:
      return self.O

    value = sum([self.board[i][2 - i] for i in range(3)])  # checking the secondary diagonal
    if value == 3:
      return self.X
    elif value == -3:
      return self.O

    for i in range(3):  # checking columns
      val = 0
      for j in range(3):
        val += self.board[j][i]

      if val == 3:
        return self.X
      elif val == -3:
        return self.O

    if all([i != 0 for s in self.board for i in s]):  # checking for a tie
      return self.tie

    return None  # the game didn't end

  def stop(self):
    for child in filter(lambda c: not c.disabled, self.children):
      child.disabled = True

    self.stopped = True
    return super().stop()

  async def on_timeout(self):
    if not self.stopped:
        self.stop()
        await self.message.edit(content="Time's up", view=self)

class Fun(commands.Cog):
  """
  Entertain people to not leave ur server
  """
  def __init__(self, bot: Coffin):
    self.bot = bot
    self.wyr_questions = []

  async def cog_unload(self):
    self.bot.blacktea_matches.clear()
    return await super().cog_unload()
  
  async def start_blacktea(self: "Fun", ctx: Context):
    self.bot.blacktea_matches[ctx.guild.id] = {}
    self.bot.blacktea_messages[ctx.guild.id] = []

    embed = (
      discord.Embed(
        color=self.bot.color,
        title="BlackTea Matchmaking",
        description="The game will begin in **30** seconds. Please click the :coffee: to join the game.",
      )
      .set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
      .add_field(
        name="Goal",
        value=". ".join(
          [
            "You have **10** seconds to find a word containing the given set of letters",
            "Failure to do so, will take away a life",
            "Each player has **3** lifes",
            "The last one standing wins",
          ]
        ),
      )
    )

    view = discord.ui.View(timeout=30)

    async def on_timeout():
      view.children[0].disabled = True
      with suppress(discord.NotFound):
        await view.message.edit(view=view)

    view.on_timeout = on_timeout
    button = BlackteaButton()
    view.add_item(button)

    view.message = await ctx.reply(embed=embed, view=view)
    self.bot.blacktea_messages[ctx.guild.id].append(view.message)
    await asyncio.sleep(30)

    if len(button.users) < 2:
      self.bot.blacktea_matches.pop(ctx.guild.id, None)
      self.bot.blacktea_messages.pop(ctx.guild.id, None)
      return await ctx.alert("There are not enough players")

    self.bot.blacktea_matches[ctx.guild.id] = {user: 3 for user in button.users}
    words = list(
      filter(
        lambda w: len(w) > 2,
        open("./structure/wordlist.txt").read().splitlines(),
      )
    )

    while len(self.bot.blacktea_matches[ctx.guild.id].keys()) > 1:
      for user in button.users:
        word = random.choice(words)
        e = discord.Embed(
          description=f":coffee: <@{user}> Say a word containing **{word[:3].upper()}**"
        )
        m = await ctx.send(embed=e)
        self.bot.blacktea_messages[ctx.guild.id].append(m)

        try:
          message = await self.bot.wait_for(
            "message",
            timeout=10,
            check=lambda msg: (
              msg.author.id == user
              and msg.channel.id == ctx.channel.id
              and word[:3].lower() in msg.content.lower().strip()
              and msg.content.lower() in [w.lower() for w in words]
            ),
          )

          await message.add_reaction("✅")
          self.bot.blacktea_messages[ctx.guild.id].append(message)
        except asyncio.TimeoutError:
          lifes = self.bot.blacktea_matches[ctx.guild.id].get(user)
          if lifes - 1 == 0:
            e = discord.Embed(description=f"☠️ <@{user}> You're eliminated")
            m = await ctx.send(embed=e)
            self.bot.blacktea_messages[ctx.guild.id].append(m)
            self.bot.blacktea_matches[ctx.guild.id].pop(user)
            button.users.remove(user)

            if len(self.bot.blacktea_matches[ctx.guild.id].keys()) == 1:
              break
          else:
            self.bot.blacktea_matches[ctx.guild.id][user] = lifes - 1
            e = discord.Embed(
              description=f"🕰️ <@{user}> Time's up. **{lifes-1}** life(s) remaining"
            )
            m = await ctx.send(embed=e)
            self.bot.blacktea_messages[ctx.guild.id].append(m)

    user = button.users[0]
    embed = discord.Embed(description=f"👑 <@{user}> Won the game")
    await gather(*[
      ctx.channel.delete_messages(chunk)
      for chunk in (
        self.bot.blacktea_messages[ctx.guild.id][i:i + 99]
        for i in range(0, len(self.bot.blacktea_messages[ctx.guild.id]), 99)
      )]
    )
    self.bot.blacktea_matches.pop(ctx.guild.id, None)
    self.bot.blacktea_messages.pop(ctx.guild.id, None)
    return await ctx.send(embed=embed)
  
  @commands.Cog.listener()
  async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
    if result := await self.bot.db.fetchrow("SELECT * FROM counting WHERE guild_id = $1", payload.guild_id):
      if payload.channel_id == result.channel_id and payload.message_id == result.last_message_id:
        channel = self.bot.get_channel(payload.channel_id)
        await channel.send(f"The last number is **{result.number}**") 

  @commands.Cog.listener()
  async def on_message(self, message: discord.Message):
    if message.guild:
      if result := await self.bot.db.fetchrow("SELECT * FROM counting WHERE guild_id = $1 AND channel_id = $2", message.guild.id, message.channel.id):
        if not ratelimiter(
          bucket=f"{message.channel.id}", key="counting", rate=1, per=3
        ):
          if len(message.content) < 10 and message.content.lower() not in ['true', 'false']:
            with suppress((KeyError, OverflowError)):
              number = numexpr.evaluate(message.content).item()
              number = int(number)
              print(f"Number {number}")
              
              if message.author.id == result.last_user:
                await message.channel.send("You are not allowed to count 2 times in a row. Restarting from **1**")
                next_count = 0
                next_author = None 
                next_message = None
              else: 
                if number == result.number+1: 
                  await message.add_reaction("✅")
                  next_count = number
                  next_author = message.author.id 
                  next_message = message.id
                else:
                  await message.channel.send(f"Expected number was **{result.number1}**. Restarting from **1**")
                  next_count = 0
                  next_author = None 
                  next_message = None
              
              await self.bot.db.execute(
                """
                UPDATE counting 
                SET number = $1,
                last_user = $2,
                last_message_id = $3
                WHERE guild_id = $4
                """,
                next_count,
                next_author,
                next_message,
                message.guild.id
              )

  @commands.command()
  async def choose(self: "Fun", ctx: Context, *, choices: str):
    """
    Pick a choice out of all choices separated by ,
    """
    choice = random.choice(choices.split(", "))
    return await ctx.neutral(f"**Choice**: {choice}")

  @commands.command(example="do you like me?, yes, no")
  async def poll(self: "Fun", ctx: Context, *, text: str):
    """
    Create a poll
    """
    try:
      question, answers = text.split(", ", maxsplit=1)
    except Exception:
      return await ctx.send_help(ctx.command)

    answers = answers.split(", ")
    if len(answers) < 2:
      return await ctx.send_help(ctx.command)

    poll = discord.Poll(question=question, duration=datetime.timedelta(days=1))
    for answer in answers:
      poll.add_answer(text=answer)

    await ctx.message.delete()
    return await ctx.send(poll=poll)

  @commands.command(aliases=["wyr"])
  async def wouldyourather(self: "Fun", ctx: Context):
    """
    Ask an wouldyourather question
    """
    question = random.choice(self.wyr_questions)[len("Would you rather ") :]
    x, y = question.split(" or ")
    await ctx.send(
      "\n".join(
        [
          "# Would you rather:",
          f"1️⃣ {x.capitalize()}",
          "**OR**",
          f"2️⃣ {y[:-1].capitalize()}",
        ]
      )
    )

  @wouldyourather.before_invoke
  async def wyr_invoke(self, _):
    if not self.wyr_questions:
      x = await self.bot.session.get(
        "https://randomwordgenerator.com/json/question-would-you-rather.json"
      )
      self.wyr_questions = list(
        map(lambda m: m["question_would_you_rather"], x.data.all)
      )

  @commands.hybrid_command()
  @discord.app_commands.allowed_installs(guilds=True, users=True)
  @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def randomhex(self: "Fun", ctx: Context):
    """
    Get a random hex code
    """
    def r(): 
      return random.randint(0, 255)

    hex_code = "#%02X%02X%02X" % (r(), r(), r())
    color = discord.Color.from_str(hex_code)
    embed = (
      discord.Embed(color=color, title=f"Showing hex code: {hex_code}")
      .set_thumbnail(
        url=f"https://singlecolorimage.com/get/{hex_code[1:]}/400x400"
      )
      .add_field(name="RGB value", value=", ".join(map(str, color.to_rgb())))
    )
    return await ctx.reply(embed=embed)

  @commands.hybrid_command()
  @discord.app_commands.allowed_installs(guilds=True, users=True)
  @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def gayrate(
    self: "Fun", ctx: Context, *, member: discord.Member = commands.Author
  ):
    """
    Gayrate a member
    """
    rate = random.randint(0, 100)
    return await ctx.neutral(f"{member.mention} is **{rate}%** gay")
  
  @commands.hybrid_command(aliases=["insult"])
  @discord.app_commands.allowed_installs(guilds=True, users=True)
  @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def pack(self: "Fun", ctx: Context, *, member: discord.User):
    """
    Insult a member
    """
    if member == ctx.author:
      return await ctx.reply("Why do you want to pack yourself ://")

    if member == self.bot.user:
      return await ctx.reply("Why do you want to pack me :((((")

    result = await self.bot.session.get(
      "https://evilinsult.com/generate_insult.php?lang=en&type=json"
    )
    await ctx.send(
      f"{member.mention} {result.insult}",
      allowed_mentions=discord.AllowedMentions.none(),
    )

  @commands.hybrid_command()
  @commands.bot_has_permissions(attach_files=True)
  async def cat(self: "Fun", ctx: Context):
    """
    Send a random cat image
    """
    buffer = BytesIO(await self.bot.session.get("https://cataas.com/cat"))
    return await ctx.reply(file=discord.File(buffer, filename="cat.png"))

  @commands.hybrid_command()
  async def dadjoke(self: "Fun", ctx: Context):
    """
    Get a random dad joke
    """
    x = await self.bot.session.get(
      "https://icanhazdadjoke.com/", headers={"Accept": "application/json"}
    )
    return await ctx.neutral(x.joke)

  @commands.hybrid_command(aliases=["ttt"])
  async def tictactoe(self: "Fun", ctx: Context, *, member: discord.Member):
    """
    Play a tictactoe game with a member
    """
    if member.bot:
      return await ctx.alert("You cannot play with a bot")
    elif member == ctx.author:
      return await ctx.alert("You cannot play with yourself")

    view = TicTacToe(ctx.author, member)
    view.message = await ctx.send(
      f"It's {ctx.author.mention}'s turn",
      view=view,
      allowed_mentions=discord.AllowedMentions.none(),
    )
  
  @commands.hybrid_command()
  async def marry(
    self, 
    ctx: Context,
    *,
    member: discord.Member
  ):
    """
    Marry someone
    """
    if await self.bot.db.fetchrow(
      """
      SELECT * FROM marry WHERE 
      first_user = $1 OR second_user = $1  
      """,
      ctx.author.id
    ):
      return await ctx.alert("You are already married...")

    if await self.bot.db.fetchrow(
      """
      SELECT * FROM marry WHERE 
      first_user = $1 OR second_user = $1  
      """,
      member.id
    ):
      return await ctx.alert(f"{member.mention} is already married...")

    async def yes(interaction: discord.Interaction):
      embed = interaction.message.embeds[0]
      if await self.bot.db.fetchrow(
        """
        SELECT * FROM marry WHERE 
        first_user = $1 OR second_user = $1  
        """,
        ctx.author.id
      ) or await self.bot.db.fetchrow(
        """
        SELECT * FROM marry WHERE 
        first_user = $1 OR second_user = $1  
        """,
        member.id
      ):
        embed.description = "This marriage cannot be initiated..."
        return await interaction.response.edit_message(embed=embed, view=None)    

      await interaction.client.db.execute(
        """
        INSERT INTO marry 
        (first_user, second_user) 
        VALUES ($1,$2)  
        """,
        ctx.author.id, interaction.user.id
      )

      embed.description = f"{interaction.user.mention} accepted the proposal. yippeee !!"
      return await interaction.response.edit_message(embed=embed, view=None)

    async def no(interaction: discord.Interaction):
      embed = interaction.message.embeds[0]
      embed.description = f"I'm sorry, but {interaction.user.mention} might not be the one for you"
      return await interaction.response.edit_message(embed=embed, view=None)

    return await ctx.confirmation(
      f"{member.mention} do you want to marry {ctx.author.mention}",
      yes, no,
      view_author=member
    )
  
  @commands.hybrid_command()
  async def divorce(self, ctx: Context):
    """
    Divorce your partner
    """
    if not (result := await self.bot.db.fetchrow(
      """
      SELECT * FROM marry WHERE 
      first_user = $1 OR second_user = $1  
      """,
      ctx.author.id
    )):
      return await ctx.alert("You are not married")
    
    async def yes(interaction: discord.Interaction):
      await interaction.client.db.execute(
        """
        DELETE FROM marry
        WHERE first_user = $1
        OR second_user = $1
        """,
        interaction.user.id
      )
      embed = interaction.message.embeds[0]
      embed.description = "Succesfully divorced your partner"
      return await interaction.response.edit_message(embed=embed, view=None)
    
    partner = result.second_user if ctx.author.id == result.first_user else result.first_user 
    await ctx.confirmation(
      f"Are you sure you want to divorce <@{partner}>\nY'all are married since {discord.utils.format_dt(result.since, style='R')}",
      yes
    )
  
  @commands.hybrid_command()
  async def marriage(
    self, 
    ctx: Context,
    *,
    member: discord.Member = commands.Author
  ):
    """
    Check how long have you been married with your partner for
    """
    if not (result := await self.bot.db.fetchrow(
      """
      SELECT * FROM marry
      WHERE first_user = $1
      OR second_user = $1   
      """,
      member.id
    )):
      return await ctx.alert("You aren't married" if member == ctx.author else f"**{member}** is **not** married")
    
    partner = result.second_user if result.first_user == member.id else result.first_user
    return await ctx.neutral(
      f"{member.mention} married <@{partner}> {discord.utils.format_dt(result.since, style='R')}"
    )

  @commands.hybrid_group()
  @discord.app_commands.allowed_installs(guilds=True, users=True)
  @discord.app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
  async def media(self, ctx: Context):
    """ 
    Manipulate images
    """
    return await ctx.send_help(ctx.command)
  
  @media.command(name="caption")
  async def media_caption(
    self,
    ctx: Context,
    image: discord.Attachment,
    *,
    caption: str
  ):
    """
    Add caption to an image
    """
    if image.content_type not in ['image/png', 'image/jpeg']:
      return await ctx.alert("Invalid attachment given!")

    img = Image.open(BytesIO(await image.read()))
    w, h = img.size 

    caption_background = Image.new("RGB", (w, int(h/4)), color="white")
    font_size = max(20, int(int(h / 4) * 0.3))
    font = ImageFont.truetype("./structure/fonts/seguibl.ttf", font_size)
    draw = ImageDraw.Draw(caption_background)
    width, height = caption_background.size
    draw.text(
      (width/2, height/2),
      caption[:32],
      (0, 0, 0),
      font=font,
      align="center",
      anchor="mm",
      embedded_color=True
    )

    background = Image.new("RGBA", (w, h+int(h/4)))
    background.paste(caption_background, (0, 0))
    background.paste(img, (0, int(h/4)))
    
    buffer = BytesIO()
    background.save(buffer, format="png")
    buffer.seek(0)
    file=discord.File(buffer, filename="image.png")
    return await ctx.send(file=file)
  
  @media.command(name="pixelate")
  async def media_pixelate(
    self,
    ctx: Context,
    image: discord.Attachment
  ):
    """
    Pixelate your image
    """
    if image.content_type not in ['image/png', 'image/jpeg']:
      return await ctx.alert("Invalid attachment given!")
    
    img = Image.open(BytesIO(await image.read()))
    small_img = img.resize((16, 16), resample=Image.Resampling.BILINEAR)
    result = small_img.resize(img.size, resample=Image.Resampling.NEAREST)

    buffer = BytesIO()
    result.save(buffer, format="png")
    buffer.seek(0)

    file = discord.File(buffer, filename="pixelated.png")
    return await ctx.send(file=file)
  
  @media.command(name="blur")
  async def media_blur(
    self,
    ctx: Context,
    image: discord.Attachment
  ):
    """
    Blur your image
    """
    if image.content_type not in ['image/png', 'image/jpeg']:
        return await ctx.alert("Invalid attachment given!")
    
    img = Image.open(BytesIO(await image.read()))
    result = img.filter(ImageFilter.GaussianBlur(10))

    buffer = BytesIO()
    result.save(buffer, format="png")
    buffer.seek(0)

    file = discord.File(buffer, filename="blurred.png")
    return await ctx.send(file=file)
  
  @media.command(name="grayscale")
  async def media_grayscale(
    self,
    ctx: Context,
    image: discord.Attachment
  ):
    """
    Grayscale your image
    """
    if image.content_type not in ['image/png', 'image/jpeg']:
        return await ctx.alert("Invalid attachment given!")
    
    img = Image.open(BytesIO(await image.read()))
    result = ImageOps.grayscale(img)

    buffer = BytesIO()
    result.save(buffer, format="png")
    buffer.seek(0)

    file = discord.File(buffer, filename="grayscaled.png")
    return await ctx.send(file=file)
  
  @media.command(name="invert")
  async def media_invert(
    self,
    ctx: Context,
    image: discord.Attachment
  ):
    """
    Invert the colors in your image
    """
    if image.content_type not in ['image/png', 'image/jpeg']:
      return await ctx.alert("Invalid attachment given!")
    
    img = Image.open(BytesIO(await image.read()))
    rgb_image = Image.merge("RGB", img.split())
    result = ImageOps.invert(rgb_image)

    buffer = BytesIO()
    result.save(buffer, format="png")
    buffer.seek(0)

    file = discord.File(buffer, filename="inverted.png")
    return await ctx.send(file=file)
  
  @media.command(name="transparent")
  async def media_transparent(
    self,
    ctx: Context,
    image: discord.Attachment
  ):
    """
    Remove an image background
    """
    if image.content_type not in ['image/png', 'image/jpeg']:
      return await ctx.alert("Invalid attachment given!")
    
    data = await image.read()
    rembg = await asyncio.to_thread(remove, data, session=session)
    
    buffer = BytesIO(rembg)
    file = discord.File(buffer, filename="transparent.png")
    return await ctx.send(file=file)
  
  @commands.command()
  async def quote(self: "Fun", ctx: Context, *, message: str):
    """
    Make ur message a quote
    """
    width, height = 800, 400
    img = Image.new("RGB", (width, height), "black")

    avatar = Image.open(BytesIO(await ctx.author.avatar.read()))
    size = (250, 250)
    avatar = avatar.resize(size)

    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size[0], size[1]), fill=255)
    avatar.putalpha(mask)

    img.paste(avatar, (80, 75), avatar)

    font = ImageFont.truetype("./structure/fonts/arial.ttf", size=30)
    afont = ImageFont.truetype("./structure/fonts/arial.ttf", size=15)

    ab = afont.getbbox(f"- @{ctx.author.name}")

    draw = ImageDraw.Draw(img)
    draw.text((75 + (size[0] - ab[2] - ab[0]) // 2, 75 + size[1] + 20), f"- @{ctx.author.name}", fill="white", font=afont)

    wrap = textwrap.fill(message, width=35).split("\n")

    y = 120
    for line in wrap:
      x = width // 2 + (width // 2 - font.getlength(line)) // 2
      draw.text((x, y), line, fill="white", font=font)
      y += 25

    buffer = BytesIO()
    img.save(buffer, format="png")
    buffer.seek(0)
    file=discord.File(buffer, filename="quote.png")
    return await ctx.reply(
      file=file
    )

  @commands.hybrid_command()
  async def typerace(self: "Fun", ctx: Context):
    """
    Test your typing speed and accuracy
    """
    def chunks(array: List[str], count: int):
      for i in range(0, len(array), count):
        yield array[i:i + count]
    
    img = Image.new("RGB", color="black", size=(500, 250))
    width, height = img.size
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("./structure/fonts/seguibl.ttf", 20)
    
    sentences = await self.bot.session.get("https://randomwordgenerator.com/json/sentences.json")
    sentences: List[str] = list(map(lambda s: s['sentence'].lower(), sentences['data']))
    sentence: str = random.choice(sentences)
    clean_text = sentence[:-1]
    text = "\n".join([" ".join(w) for w in chunks(sentence.split(" "), 4)])

    draw.text(
      (width/2, height/2),
      text[:-1],
      (255, 255, 255),
      font=font,
      align="center",
      anchor="mm"
    )

    buffer = BytesIO()
    img.save(buffer, format="png")
    buffer.seek(0)
    file = discord.File(buffer, filename="typerace.png")

    message = await ctx.send(
      "You have **30** seconds to type the text below:",
      file=file
    )
    
    try:
      response = await self.bot.wait_for(
        'message',
        check=lambda m: bool(
          m.author.id == ctx.author.id and 
          m.channel.id == ctx.channel.id and 
          m.content != ''
        ),
        timeout=30
      )
    except asyncio.TimeoutError: 
      return await ctx.send(f"{ctx.author.mention}: You didn't send the message in time 🙁")
    
    accuracy = round(SequenceMatcher(None, clean_text, response.content).ratio() * 100, 2)
    speed = round((response.created_at - message.created_at).total_seconds(), 2)
    wpm = round(60/speed*len(response.content.split(" ")), 2)
    embed = discord.Embed(
      title="Your typing results",
      color=self.bot.color,
      description=f"Accuracy: `{accuracy}%`\nSpeed: `{speed}` seconds\nWPM: `{wpm}`"
    )\
    .set_author(
      name=ctx.author.name,
      icon_url=ctx.author.display_avatar.url
    )

    return await response.reply(embed=embed)

  @commands.hybrid_group(invoke_without_command=True)
  @commands.blacktea_round()
  async def blacktea(self: "Fun", ctx: Context):
    """
    Play a match of blacktea
    """
    return await create_task(self.start_blacktea(ctx), name=f"blacktea-{ctx.guild.id}")
  
  @blacktea.command(name="end")
  @commands.has_permissions(manage_guild=True)
  async def blacktea_end(self: "Fun", ctx: Context):
    """
    Stop the current blacktea game
    """
    task = next((t for t in all_tasks() if t.get_name() == f"blacktea-{ctx.guild.id}"), None)
    if not task:
        return await ctx.alert("There is no current blacktea game going on")

    task.cancel()
    if messages := self.bot.blacktea_messages.get(ctx.guild.id):
      await gather(*[
        ctx.channel.delete_messages(chunk)
        for chunk in (
          self.bot.blacktea_messages[ctx.guild.id][i:i + 99]
          for i in range(0, len(messages), 99)
        )]
      )
    
    try:
      await task
    except CancelledError:
      pass

    return await ctx.confirm("Cancelled the ongoing blacktea game")

  @commands.group(invoke_without_command=True)
  async def counter(self, ctx: Context):
    """
    Manage the counter game in your server
    """
    return await ctx.send_help(ctx.command)
  
  @counter.command(name="setup")
  @commands.has_permissions(manage_guild=True)
  async def counter_setup(
    self,
    ctx: Context,
    *,
    channel: discord.TextChannel
  ):
    """
    Setup the counter game
    """
    r = await self.bot.db.execute(
      """
      INSERT INTO counting (guild_id, channel_id)
      VALUES ($1,$2) ON CONFLICT (guild_id)
      DO NOTHING   
      """,
      ctx.guild.id, channel.id
    ) 
    if r == "INSERT 0":
      return await ctx.alert("The counting game is already configured in this server")
    
    await channel.send("The counting starts from **1**")
    return await ctx.confirm(f"Counting game is now available in {channel.mention}")
  
  @counter.command(name="disable")
  @commands.has_permissions(manage_guild=True)
  async def counter_disable(
    self,
    ctx: Context
  ):
    """
    Disable the counting game
    """
    r = await self.bot.db.execute(
      """
      DELETE FROM counting  
      WHERE guild_id = $1
      """,
      ctx.guild.id
    )
    if r == "DELETE 0":
      return await ctx.alert("The counting game isn't configured")
    
    return await ctx.confirm("Disabled the counting game")

async def setup(bot: Coffin) -> None:
  return await bot.add_cog(Fun(bot))