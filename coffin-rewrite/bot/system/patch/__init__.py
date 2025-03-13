from .channel import success, warning, normal, fail, reply, confirm, dump_history
from .command import *
from .context import *
from .interaction import *
from .member import config, is_donator, worker_badges, url
from .guild import *
from .alias import *
from .message import *
from .help import map_check, Help
from .checks import is_staff, is_booster, guild_owner
from .role import actual_position

import discord

discord.TextChannel.confirm = confirm
discord.TextChannel.success = success
discord.TextChannel.normal = normal
discord.TextChannel.fail = fail
discord.TextChannel.warning = warning
discord.TextChannel.reply = reply
discord.TextChannel.dump_history = dump_history

discord.Thread.confirm = confirm
discord.Thread.success = success
discord.Thread.normal = normal
discord.Thread.fail = fail
discord.Thread.warning = warning
discord.Thread.reply = reply
discord.Thread.dump_history = dump_history

discord.Member.config = config
discord.Member.url = url
discord.Member.is_donator = is_donator
discord.Member.worker_badges = worker_badges

discord.User.config = config
discord.User.url = url
discord.User.is_donator = is_donator
discord.User.worker_badges = worker_badges

discord.Role.actual_position = actual_position