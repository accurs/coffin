from discord.ext.commands import flag
from typing import Optional, Literal
from .base import Flags as FlagConverter

class ModerationFlags(FlagConverter, delimiter=" "):
	reason: Optional[str] = flag(default="No Reason provided", description="give a reason for the moderation action taken")