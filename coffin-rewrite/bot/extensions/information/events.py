
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
    Thread,
    Message
)
from datetime import datetime, timedelta
from tuuid import tuuid
from typing import List

import json

class InformationEvents(Cog):
    def __init__(self, bot: Client):
        self.bot = bot

    @Cog.listener("on_bulk_message_delete")
    async def on_purge(self, messages: List[Message]):
        """Event triggered when multiple messages are deleted at once"""
        await self.bot.db.execute(
            """
                INSERT INTO message_logs 
                (id, guild_id, channel_id, messages, created_at, expires_at) 
                VALUES($1, $2, $3, $4, $5, $6)
            """,
            tuuid(),
            messages[0].guild.id,
            messages[0].channel.id,
            json.dumps([message.to_dict() for message in messages]),
            datetime.now(),
            datetime.now() + timedelta(hours=24)
        )
                                  


async def setup(bot: Client):
    await bot.add_cog(InformationEvents(bot))