from .YouTube import extract, download, repost as repost_youtube
from discord import Message, Client




def repost(bot: Client, message: Message):
    repost_youtube(bot, message)

