import uvicorn
import os
import mimetypes
import aiohttp
import aiofiles
import datetime
import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from cache import Cache
from hashlib import md5
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

templates = Jinja2Templates(directory="templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
  app.cache = Cache()
  task = asyncio.create_task(clean())
  yield
  task.cancel()

async def clean():
  while True:
    now = datetime.datetime.now().timestamp()
    for file in os.listdir("/var/www/cdn"):
      path = os.path.join("/var/www/cdn", file)
      if os.path.isfile(path):
        modified = os.path.getmtime(path)
        if now - modified > datetime.timedelta(days=7).total_seconds():
          os.remove(path)
          app.cache.remove(file)
    await asyncio.sleep(600)

app = FastAPI(title="Coffin CDN", docs_url=None, redoc_url="/", lifespan=lifespan)
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_headers=["*"],
  allow_methods=["*"]
)

async def optimize(path: str, format: str, quality: int = 100):
  async with aiofiles.open(path, "rb") as f:
    image = Image.open(await f.read())
    image.convert("RGB")
    image.save(path, format=format, quality=quality)

@app.post("/upload")
async def upload(url: str, request: Request):
  type = request.query_params.get("type", "cdn")
  if not type in ["reskin", "cdn", "other", "harry"]:
    raise HTTPException(
      status_code=404,
      detail="Not a good type"
    )

  hashed = md5(url.encode()).hexdigest()
  ext = mimetypes.guess_type(url)[0].split('/')[1].lower()
  path = os.path.join(f"/var/www/{type}", f"{hashed}.{ext}")

  if ext not in ['png', 'jpeg', 'jpg', 'gif', 'webp', 'heic', 'heif']:
    raise HTTPException(
      status_code=400,
      detail="Unsupported file type"
    )

  async with aiohttp.ClientSession() as cs:
    async with cs.get(url) as r:
      if r.status != 200:
        raise HTTPException(status_code=404, detail="Cannot download this image")

      if int(r.headers.get("Content-Length", 0)) > 52428800:
        raise HTTPException(
          status_code=403,
          detail="Image file size too big"
        )

      temp_path = path + ".tmp"
      async with aiofiles.open(temp_path, "wb") as f:
        await f.write(await r.read())

      """if not ext == "gif":
        await optimize(temp_path, format="WEBP", quality=85)"""
  
  os.rename(temp_path, path)
  await app.cache.add(f"{hashed}.{ext}", path)
  return {"url": f"https://cdn.coffin.lol/{hashed}.{ext}"}

@app.delete("/delete", include_in_schema=False)
async def delete(url: str):
  urled = urlparse(url)
  file = os.path.basename(urled.path)
  path = os.path.join("/var/www/cdn", file)

  if os.path.exists(path):
    os.remove(path)
    app.cache.remove(file)
    return JSONResponse(content={"detail": "Image deleted"}, status_code=200)
  
  raise HTTPException(
    status_code=404,
    detail="Image not found"
  )

@app.get("/{id}.{format}", include_in_schema=False)
async def cdn(id: str, format: str, request: Request):
  file = f"{id}.{format}"

  if cache := app.cache.get(file):
    if os.path.exists(cache):
      return FileResponse(cache)
  
  for path in ['/var/www/cdn', '/var/www/reskin', '/var/www/other']:
    fpath = os.path.join(path, file)
    if os.path.exists(fpath):
      await app.cache.add(f"{id}.{format}", fpath)
      return FileResponse(fpath)
 
  return templates.TemplateResponse(
      "404.html",
      {"request": request, "code": 404, "message": "Image not found"}
    )

@app.get("/cf", include_in_schema=False)
async def cf():
  return app.cache.getall()

async def start():
  config = uvicorn.Config(
    app,
    host="127.0.0.1",
    port=6978,
    reload=True,
    log_level="info"
  )
  server = uvicorn.Server(config)
  await server.serve()

if __name__ == "__main__":
  asyncio.run(start())