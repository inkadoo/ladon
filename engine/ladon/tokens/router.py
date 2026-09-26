from fastapi import APIRouter, HTTPException, Request

from ..addresses import InvalidAddress, parse_address
from ..guard import RateLimiter, reporter_key
from .analysis import NotAToken, TokenChecker

CHECKS_PER_MINUTE = 20


def token_router(checker: TokenChecker | None, salt: str) -> APIRouter:
    router = APIRouter()
    limiter = RateLimiter(limit=CHECKS_PER_MINUTE, window_seconds=60)

    @router.get("/v1/token/{mint}/risk")
    async def token_risk(mint: str, request: Request) -> dict:
        try:
            mint = parse_address(mint)
        except InvalidAddress:
            raise HTTPException(status_code=400, detail="That is not a valid Solana token address.") from None
        if not limiter.allow(reporter_key(request.client.host if request.client else "unknown", salt)):
            raise HTTPException(status_code=429, detail="Too many checks from you just now. Please wait a minute and try again.")
        if checker is None:
            raise HTTPException(status_code=503, detail="Token checks are not available right now.")
        try:
            return await checker.check(mint)
        except NotAToken:
            raise HTTPException(status_code=400, detail="That address is not a token. Paste the token's mint address.") from None

    return router
