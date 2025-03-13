from .channels import TextChannelConverter, ThreadChannelConverter, GuildChannelConverter, CategoryChannelConverter, VoiceChannelConverter
from .snowflakes import UserConverter, MemberConverter, SafeMemberConverter, Emoji
from .roles import AssignedRole, Role, MultipleRoles, FakePermission
from .custom import Boolean, CommandConverter, Timeframe, EmbedConverter, GuildConv, GuildConverter, GConverter, Expiration, AntinukeAction #, YouTubeChannelConverter,
from .color import ColorConv, ColorInfo
from discord.ext import commands

commands.TextChannelConverter = TextChannelConverter
commands.ThreadConverter = ThreadChannelConverter
commands.GuildConverter = GuildConverter
commands.Emoji = Emoji
commands.AntinukeAction = AntinukeAction
commands.GuildChannelConverter = GuildChannelConverter
commands.CategoryChannelConverter = CategoryChannelConverter
commands.VoiceChannelConverter = VoiceChannelConverter
commands.UserConverter = UserConverter
commands.MemberConverter = MemberConverter
commands.SafeMemberConverter = SafeMemberConverter
commands.RoleConverter = Role
commands.SafeRoleConverter = AssignedRole
commands.MultipleRoles = MultipleRoles
commands.Boolean = Boolean
commands.ColourConverter = ColorConv
commands.ColorConverter = ColorConv
commands.ColorInfo = ColorInfo
#commands.YouTubeChannelConverter = YouTubeChannelConverter
commands.CommandConverter = CommandConverter
commands.Timeframe = Timeframe
commands.EmbedConverter = EmbedConverter
commands.GuildID = GConverter
commands.Expiration = Expiration
commands.FakePermission = FakePermission