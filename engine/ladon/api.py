"""Ladon's public API: look up any Solana address, and report one."""

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .addresses import InvalidAddress, parse_address
from .config import Settings, load_settings
from .db import Database
from .engine import Engine
from .exclusions import load_exclusions
from .guard import MAX_DESCRIPTION, RateLimiter, clean_description, reporter_key
from .helius import Helius
from .models import Score
from .store import MemoryStore


class ReportIn(BaseModel):
    address: str
    description: str = Field(default="", max_length=MAX_DESCRIPTION * 2)


def score_json(score: Score) -> dict:
    return {
        "address": score.address,
        "risk": score.risk,
        "confidence": score.confidence.value,
        "flagged": score.flagged,
        "reasons": [{"code": r.code, "text": r.text} for r in score.reasons],
        "cluster_size": score.cluster_size,
        "reports": score.reports,
    }


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or load_settings()
    helius = Helius(settings.helius_api_key) if settings.helius_api_key else None
    engine = engine or Engine(MemoryStore(), excluded=load_exclusions(), helius=helius)
    limiter = RateLimiter()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.database_url and engine.db is None:
            engine.db = await Database.connect(settings.database_url)
            await engine.db.migrate()
            await engine.db.load_into(engine.store)
            engine.rescore()
        yield
        if engine.db:
            await engine.db.close()
        if helius:
            await helius.close()

    app = FastAPI(title="Ladon", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    def valid(address: str) -> str:
        try:
            return parse_address(address)
        except InvalidAddress:
            raise HTTPException(status_code=400, detail="That is not a valid Solana address.") from None

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/v1/address/{address}")
    def lookup(address: str) -> dict:
        return score_json(engine.lookup(valid(address)))

    @app.post("/v1/reports", status_code=202)
    async def report(body: ReportIn, request: Request, background: BackgroundTasks) -> dict:
        address = valid(body.address)
        key = reporter_key(request.client.host if request.client else "unknown", settings.reporter_salt)
        if not limiter.allow(key):
            raise HTTPException(status_code=429, detail="Too many reports from you just now. Please try again in a few minutes.")
        await engine.report(address, key, clean_description(body.description))
        background.add_task(engine.check, address)
        return {
            "status": "received",
            "message": "Thank you. Your report starts a check of this wallet's onchain history. A report never flags a wallet on its own.",
        }

    return app


app = create_app()
