from discord import Guild, Client
from ..classes.database import Record
from typing import Optional
async def config(self: Guild) -> Optional[Record]:
    bot = self._state._get_client()
    return await bot.db.fetchrow("""SELECT * FROM config WHERE guild_id = $1""", self.id)

async def level_config(self: Guild) -> Optional[Record]:
    bot = self._state._get_client()
    return await bot.db.fetchrow("""SELECT * FROM text_level_settings WHERE guild_id = $1""", self.id)
    

Guild.config = config
Guild.level_config = level_config