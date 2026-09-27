from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .addresses import InvalidAddress, parse_address, parse_signature
from .config import Settings, load_settings
from .db import Database
from .engine import Engine
from .exclusions import load_exclusions
from .guard import MAX_DESCRIPTION, RateLimiter, clean_description, reporter_key
from .helius import Helius
from .models import Score
from .phishing import PhishingList
from .store import MemoryStore
from .tokens.analysis import TokenChecker
from .tokens.router import token_router
from .tokens.sources import DexScreener, HeliusRpc, SourceError
from .wallets.checker import WalletChecker


class ReportIn(BaseModel):
    address: str
    description: str = Field(default="", max_length=MAX_DESCRIPTION * 2)
    signature: str = Field(default="", max_length=100)


def score_json(score: Score, token_account: str | None = None) -> dict:
    return {
        "address": score.address,
        "token_account": token_account,
        "risk": score.risk,
        "confidence": score.confidence.value,
        "flagged": score.flagged,
        "reasons": [{"code": r.code, "text": r.text} for r in score.reasons],
        "cluster_size": score.cluster_size,
        "reports": score.reports,
    }


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    tokens: TokenChecker | None = None,
    wallets: WalletChecker | None = None,
    phishing: PhishingList | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    helius = Helius(settings.helius_api_key) if settings.helius_api_key else None
    engine = engine or Engine(MemoryStore(), excluded=load_exclusions(), helius=helius)
    if settings.helius_api_key and (tokens is None or wallets is None):
        rpc = HeliusRpc(settings.helius_api_key)
        tokens = tokens or TokenChecker(rpc, DexScreener(), excluded=load_exclusions())
        wallets = wallets or WalletChecker(rpc, excluded=load_exclusions())
    phishing = phishing or PhishingList()
    lookups = RateLimiter(limit=20, window_seconds=60)
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
        if tokens:
            await tokens.rpc.close()
            await tokens.dex.close()

    app = FastAPI(title="Ladon", version="0.1.0", lifespan=lifespan)
    app.include_router(token_router(tokens, settings.reporter_salt))
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    def parse_owner(owner: str) -> bool:
        try:
            parse_address(owner)
            return True
        except InvalidAddress:
            return False

    def valid(address: str) -> str:
        try:
            return parse_address(address)
        except InvalidAddress:
            raise HTTPException(status_code=400, detail="That is not a valid Solana address.") from None

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/v1/phishing/domains")
    async def phishing_domains(response: Response) -> dict:
        await phishing.refresh()
        response.headers["Cache-Control"] = "public, max-age=3600"
        return {
            "domains": phishing.domains,
            "sources": ["Phantom blocklist (MIT)", "Ladon reports"],
            "updated_at": datetime.fromtimestamp(phishing.updated_at, UTC).isoformat() if phishing.updated_at else None,
        }

    @app.get("/v1/address/{address}")
    async def lookup(address: str, request: Request) -> dict:
        address = valid(address)
        if wallets is None:
            return score_json(engine.lookup(address))
        if not lookups.allow(reporter_key(request.client.host if request.client else "unknown", settings.reporter_salt)):
            raise HTTPException(status_code=429, detail="Too many checks from you just now. Please wait a minute and try again.")
        owner = None
        try:
            owner = await wallets.rpc.token_account_owner(address)
        except SourceError:
            pass
        if owner and owner != address and parse_owner(owner):
            return score_json(await engine.investigate(owner, wallets), token_account=address)
        return score_json(await engine.investigate(address, wallets))

    @app.post("/v1/reports", status_code=202)
    async def report(body: ReportIn, request: Request, background: BackgroundTasks) -> dict:
        address = valid(body.address)
        key = reporter_key(request.client.host if request.client else "unknown", settings.reporter_salt)
        if not limiter.allow(key):
            raise HTTPException(status_code=429, detail="Too many reports from you just now. Please try again in a few minutes.")
        signature = ""
        if body.signature.strip():
            try:
                signature = parse_signature(body.signature)
            except InvalidAddress:
                raise HTTPException(status_code=400, detail="That is not a valid transaction signature.") from None
        await engine.report(address, key, clean_description(body.description), signature)
        background.add_task(engine.check, address, signature)
        return {
            "status": "received",
            "message": "Thank you. Your report starts a check of this wallet's onchain history. A report never flags a wallet on its own.",
        }

    return app


app = create_app()
