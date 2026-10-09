from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.routers import chat, network
from app.store import store

load_dotenv()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    fixture = Path(__file__).resolve().parent.parent / "fixtures" / "cas_test_zones.json"
    if fixture.exists() and not store.get().zones:
        store.load_fixture(fixture)
    yield


app = FastAPI(title="Réseau électrique TriPhase", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(network.router)
app.include_router(chat.router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
