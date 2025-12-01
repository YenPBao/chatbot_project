# src/app/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from app.controller.auth import router as auth_router
from app.controller.conversation import router as conv_router
from app.core.db import engine, Base
import uvicorn

app = FastAPI(title="JWT Auth Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "resources" / "static"
TEMPLATES_DIR = BASE_DIR / "resources" / "templates"

if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.on_event("startup")
async def _create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(auth_router)
app.include_router(conv_router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
