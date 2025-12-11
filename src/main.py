# src/app/main.py
from fastapi import FastAPI
from pathlib import Path
from app.controller.auth import router as auth_router
from app.controller.conversation import router as conv_router
from app.core.db import engine, Base
import uvicorn

app = FastAPI(title="Chatbot_project")

BASE_DIR = Path(__file__).resolve().parent


@app.on_event("startup")
async def _create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


app.include_router(auth_router)
app.include_router(conv_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
