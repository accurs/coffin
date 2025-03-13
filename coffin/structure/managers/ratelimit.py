from discord.ext.commands import CooldownMapping

from typing import (
  Any,
  Dict,
  Optional
)

mappings: Dict[str, CooldownMapping] = {}

def handle_bucket(key: Any) -> Any:
  return key

def ratelimiter(bucket: str, key: Any, rate: int, per: float) -> Optional[int]:
  mapping = mappings.setdefault(
    bucket, CooldownMapping.from_cooldown(rate, per, handle_bucket)
  )

  return mapping.get_bucket(key).update_rate_limit()