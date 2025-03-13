from io import BytesIO
from asyncio import TimeoutError
from contextlib import suppress
from discord.ext.commands import Context as DefaultContext
from discord.ui import Button, View

from discord import (
  ButtonStyle,
  Embed,
  HTTPException,
  Interaction,
  Message,
  File,
  NotFound
)
from typing import (
  Union,
  List
)
from structure.config import Paginator as pag

class PaginatorButton(Button):
  def __init__(self, emoji: str, style: ButtonStyle) -> None:
    super().__init__(
      emoji=emoji,
      style=style,
      custom_id=emoji,
    )
    self.disabled: bool = False

  async def callback(self, interaction: Interaction) -> None:
    await interaction.response.defer()
    if self.custom_id in [pag.previous, pag.next]:
      self.view.current_page = (self.view.current_page + (1 if self.custom_id == pag.next else -1)) % len(self.view.pages)

    elif self.custom_id == pag.navigate:
      for child in self.view.children:
        child.disabled = True

      await interaction.message.edit(view=self.view)
      prompt = await interaction.neutral("What page would you like to go to?")

      try:
        response = await self.view.ctx.bot.wait_for(
          "message",
          timeout=6,
          check=lambda m: m.author.id == interaction.user.id
          and m.channel.id == interaction.channel.id
          and m.content
          and m.content.isdigit()
          and int(m.content) <= len(self.view.pages)
          and int(m.content) > 0,
        )

        self.view.current_page = int(response.content) - 1
        for child in self.view.children:
          child.disabled = False

        await interaction.message.edit(view=self.view)
          
        with suppress(HTTPException):
          await prompt.delete()
          await response.delete()
      except TimeoutError:
        for child in self.view.children:
          child.disabled = False

        await interaction.message.edit(view=self.view)
        await prompt.delete()
    elif self.custom_id == pag.cancel:
      with suppress(HTTPException):
        await interaction.message.delete()

      return
    
    if getattr(self.view, "type", None):
      page = self.view.pages[self.view.current_page]
      if self.view.type == "embed":
        await self.view.message.edit(embed=page, view=self.view)
      else:
        await self.view.message.edit(content=page, view=self.view)

class Paginator(View):
  def __init__(self, ctx: DefaultContext, pages: List[Union[Embed, str]]) -> None:
    super().__init__()
    self.ctx: DefaultContext = ctx
    self.current_page: int = 0
    self.pages: List[Union[Embed, str]] = pages
    self.message: Message
    self.add_initial_buttons()

  def add_initial_buttons(self) -> "Paginator":
    for button in (
      PaginatorButton(
        emoji=pag.previous,
        style=ButtonStyle.blurple,
      ),
      PaginatorButton(
        emoji=pag.next,
        style=ButtonStyle.blurple,
      ),
      PaginatorButton(
        emoji=pag.navigate,
        style=ButtonStyle.grey,
      ),
      PaginatorButton(
        emoji=pag.cancel,
        style=ButtonStyle.red,
      ),
    ):
      self.add_item(button)

    return self

  @property
  def type(self) -> str:
    return "embed" if isinstance(self.pages[0], Embed) else "text"

  async def send(self, content: Union[str, Embed], **kwargs) -> Message:
    if self.type == "embed":
      return await self.ctx.send(embed=content, **kwargs)
    else:
      return await self.ctx.send(content=content, **kwargs)

  async def interaction_check(self, interaction: Interaction) -> bool:
    if interaction.user.id != self.ctx.author.id:
      await interaction.alert("You cannot use these buttons!")
    return interaction.user.id == self.ctx.author.id

  async def on_timeout(self) -> None:
    for child in self.children:
      child.disabled = True
    
    with suppress(NotFound):
      await self.message.edit(view=self)

  async def begin(self) -> Message:
    if len(self.pages) == 1:
      self.message = await self.send(self.pages[0])
    else:
      self.message = await self.send(self.pages[self.current_page], view=self)

    return self.message

class FileButton(PaginatorButton):
  async def callback(self, interaction: Interaction):
    await super().callback(interaction)
    page = self.view.pages[self.view.current_page]
    buffer = BytesIO(await interaction.client.session.get(page['media_url']))
    
    if page['media_type'] == 0:
      filename = "snap.png"
    else:
      filename = "snap.mp4"
    
    return await interaction.message.edit(
      content=page['content'],
      attachments=[File(buffer, filename=filename)],
      view=self.view
    )

class PaginatorFiles(View):
  def __init__(self, ctx: DefaultContext, pages: List[dict]):
    super().__init__()
    self.ctx: DefaultContext = ctx
    self.current_page: int = 0
    self.pages = pages
    self.add_initial_buttons()
  
  def add_initial_buttons(self) -> "PaginatorFiles":
    for button in (
      FileButton(
        emoji=pag.previous,
        style=ButtonStyle.blurple,
      ),
      FileButton(
        emoji=pag.next,
        style=ButtonStyle.blurple,
      ),
      FileButton(
        emoji=pag.navigate,
        style=ButtonStyle.grey,
      ),
      FileButton(
        emoji=pag.cancel,
        style=ButtonStyle.red,
      ),
    ):
      self.add_item(button)
  
  async def on_timeout(self) -> None:
    for child in self.children:
      child.disabled = True
    
    with suppress(NotFound):
      await self.message.edit(view=self)
  
  async def start(self):
    page = self.pages[self.current_page]
    buffer = BytesIO(await self.ctx.bot.session.get(page['media_url']))
    
    if page['media_type'] == 0:
      filename = "snap.png"
    else:
      filename = "snap.mp4"
    
    kwargs = {
      "content": page['content'],
      "file": File(buffer, filename=filename),
      "view": self
    }
    self.message = await self.ctx.send(**kwargs)

  async def interaction_check(self, interaction: Interaction) -> bool:
    if interaction.user.id != self.ctx.author.id:
      await interaction.response.defer(ephemeral=True)
    return interaction.user.id == self.ctx.author.id