from collections.abc import Callable

import asyncpg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .addresses import InvalidAddress, parse_address
from .airdrop_auth import AirdropAuth, bearer, digest
from .airdrop_social import REWARDS, SocialQuests
from .config import Settings
from .guard import reporter_key


class ChallengeIn(BaseModel):
    wallet: str = Field(max_length=44)


class VerifyIn(ChallengeIn):
    nonce: str = Field(max_length=100)
    signature: str = Field(max_length=100)


class XCompleteIn(BaseModel):
    state: str = Field(max_length=100)
    code: str = Field(max_length=1000)


class QuestIn(BaseModel):
    task: str = Field(max_length=32)
    url: str = Field(default="", max_length=500)


def identity_router(pool: Callable[[], asyncpg.Pool], settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1/airdrop")

    async def identity(request: Request, write: bool = False) -> tuple[str, str]:
        token = bearer(request)
        auth = AirdropAuth(pool())
        wallet = await auth.wallet(token)
        if write:
            await auth.limit("social:" + wallet, maximum=10)
        return wallet, token

    async def auth_limit(request: Request) -> None:
        key = reporter_key(request.client.host if request.client else "unknown", settings.reporter_salt)
        await AirdropAuth(pool()).limit("auth:" + key)

    @router.get("/campaign")
    async def campaign() -> dict:
        return {"x_enabled": bool(settings.x_client_id and settings.x_client_secret and settings.airdrop_encryption_key), "rewards": REWARDS}

    @router.post("/auth/challenge")
    async def challenge(body: ChallengeIn, request: Request) -> dict:
        try:
            wallet = parse_address(body.wallet)
        except InvalidAddress:
            raise HTTPException(400, "That is not a valid Solana address.") from None
        origin = request.headers.get("origin", "")
        if origin not in settings.allowed_origins:
            raise HTTPException(403, "Sign in from the Ladon website.")
        await auth_limit(request)
        return await AirdropAuth(pool()).challenge(wallet, origin)

    @router.post("/auth/verify")
    async def verify(body: VerifyIn, request: Request) -> dict:
        await auth_limit(request)
        try:
            wallet = parse_address(body.wallet)
        except InvalidAddress:
            raise HTTPException(400, "That is not a valid Solana address.") from None
        return await AirdropAuth(pool()).verify(wallet, body.nonce, body.signature)

    @router.get("/auth/session")
    async def session(request: Request) -> dict:
        wallet, _ = await identity(request)
        return {"wallet": wallet}

    @router.post("/auth/logout")
    async def logout(request: Request) -> dict:
        await pool().execute("delete from airdrop_sessions where token_hash = $1", digest(bearer(request)))
        return {"ok": True}

    @router.get("/quests")
    async def status(request: Request) -> dict:
        wallet, _ = await identity(request)
        return await SocialQuests(pool(), settings).status(wallet)

    @router.post("/x/start")
    async def start(request: Request) -> dict:
        wallet, token = await identity(request, True)
        return await SocialQuests(pool(), settings).start(wallet, token)

    @router.post("/x/complete")
    async def complete(body: XCompleteIn, request: Request) -> dict:
        wallet, token = await identity(request, True)
        service = SocialQuests(pool(), settings)
        await service.complete(wallet, token, body.state, body.code)
        return await service.status(wallet)

    @router.post("/quests/claim")
    async def claim(body: QuestIn, request: Request) -> dict:
        wallet, _ = await identity(request, True)
        service = SocialQuests(pool(), settings)
        awarded = await service.claim(wallet, body.task, body.url)
        return {"awarded": awarded, "quests": await service.status(wallet)}

    @router.post("/x/disconnect")
    async def disconnect(request: Request) -> dict:
        wallet, _ = await identity(request, True)
        service = SocialQuests(pool(), settings)
        await service.disconnect(wallet)
        return await service.status(wallet)

    return router
