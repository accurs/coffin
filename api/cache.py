import asyncio

from typing import Any, Optional

class Cache():
  def __init__(self: "Cache"):
    self.inventory = {}

  async def do_expiration(self, key: str, time: int):
    await asyncio.sleep(time)
    self.remove(key)

  async def add(
    self: "Cache", key: str, value: Any, expiring: Optional[int] = None
  ) -> Any:
    self.inventory[key] = value

    if expiring:
      asyncio.ensure_future(self.do_expiration(key, expiring))

    return value

  def remove(self, key: str):
    if self.get(key):
      return self.inventory.pop(key)

  def get(self, key: str) -> Any:
    return self.inventory.get(key)
  
  def getall(self):
    return self.inventory