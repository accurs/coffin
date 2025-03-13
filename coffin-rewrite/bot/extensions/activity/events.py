from discord.ext.commands import (
    Cog
)
from discord import (
    Client,
    User,
    Member,
    Guild
)

class ActivityEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

async def setup(bot: Client):
    await bot.add_cog(ActivityEvents(bot))