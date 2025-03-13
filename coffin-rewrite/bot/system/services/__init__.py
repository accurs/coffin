from .bot import *
from .manipulation import *
from .socials import *
from .media import *


from DataProcessing.client import ServiceManager
from discord import Client

async def setup(bot: Client) -> bool:
    """this is for DataProcessing (which is a package i will maintain just so you know)
    it is used to get scrape data from web services like google, brave etc"""
    bot.services = ServiceManager(bot.redis, None)
    return True