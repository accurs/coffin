from system.coffin import Coffin
from gc import get_referents
from system.classes.builtins import calculate_, maximum, minimum, maximum_, minimum_, positive, positive_, hyperlink, shorten as shorten_, ObjectTransformer, catch, asDict, suppress_error, get_error, boolean_to_emoji, shorten__, chunk, number, human_timedelta, human_join, humanize, humanize_
import warnings
import builtins

warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.simplefilter("ignore", ResourceWarning)

"""
Overriding builtins in python's memory
"""
builtins.human_join = human_join
builtins.human_timedelta = human_timedelta
builtins.boolean_to_emoji = boolean_to_emoji
builtins.calculate = calculate_
builtins.catch = catch
builtins.get_error = get_error
builtins.suppress_error = suppress_error
builtins.hyperlink = hyperlink
builtins.ObjectTransformer = ObjectTransformer
builtins.asDict = asDict
_float = get_referents(float.__dict__)[0]
_str = get_referents(str.__dict__)[0]
_int = get_referents(int.__dict__)[0]
_list = get_referents(list.__dict__)[0]
__list = get_referents(builtins.list.__dict__)[0]
__float = get_referents(builtins.float.__dict__)[0]
__int = get_referents(builtins.int.__dict__)[0]
__str = get_referents(builtins.str.__dict__)[0]
_float["maximum"] = maximum
_float["minimum"] = minimum
_float["positive"] = positive
__float["maximum"] = maximum
__float["minimum"] = minimum
__float["positive"] = positive
_int["maximum"] = maximum_
_int["humanize"] = humanize
_list["chunk"] = chunk
__list["chunk"] = chunk
_list["number"] = number
__list["number"] = number
_int["minimum"] = minimum_
_int["positive"] = positive_
__int["maximum"] = maximum_
__int["minimum"] = minimum_
__int["humanize"] = humanize
__int["positive"] = positive_
_str["shorten"] = shorten__
_str["humanize"] = humanize_
__str["humanize"] = humanize_
__str["shorten"] = shorten__
builtins.shorten = shorten_


"""
Bot Initialization
"""

bot = Coffin()

if __name__ == "__main__":
    bot.run()
