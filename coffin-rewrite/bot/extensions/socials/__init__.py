
from .events import SocialEvents
from .commands import Socials

async def setup(bot):
    await bot.add_cog(SocialEvents(bot))
    await bot.add_cog(Socials(bot))