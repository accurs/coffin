from cashews import cache
from typing import Coroutine, Callable, Any
import functools

cache.setup("mem://")