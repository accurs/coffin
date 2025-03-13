
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
from asyncio import ensure_future
from system.patch.context import Context
from loguru import logger
from logging import getLogger

log = getLogger(__name__)

def l(message: str):
    log.info(message)
    logger.info(message)

class FunEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot
        self._last_message = None

    @Cog.listener("on_valid_message")
    async def add_message_history(self, ctx: Context):
        ensure_future(self.bot.redis.add_message(ctx.message))

    @Cog.listener("on_redis_message")
    async def redis_message(self, message):
        self._last_message = message
        l(f"received message from redis: {message}")

async def setup(bot: Client):
    await bot.add_cog(FunEvents(bot))