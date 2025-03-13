from logging import INFO, basicConfig, FileHandler, StreamHandler, getLogger

g = "\033[92m"
r = "\033[0m"
red = "\033[0;31m"

basicConfig(
  level=INFO,
  format=f"[%(levelname)s] {g}(%(asctime)s){r} @ {red}%(module)s{r} -> %(message)s",
  datefmt="%Y-%m-%d %H:%M",
  handlers=[
    FileHandler(filename="bot.log", encoding='utf-8'),
    StreamHandler()
  ]
)
