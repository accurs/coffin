
from discord.ext.commands import (
    CommandError,
    Cog,
    group,
    command,
    has_permissions
)
from discord import (
    Client,
    Embed,
    File,
    User,
    Member,
    Guild,
    TextChannel,
    Thread
)

class Economy(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

async def setup(bot: Client):
    await bot.add_cog(Economy(bot))