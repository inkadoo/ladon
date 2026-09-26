from fastapi import APIRouter, HTTPException

from ..addresses import InvalidAddress, parse_address
from .analysis import NotAToken, TokenChecker


def token_router(checker: TokenChecker | None) -> APIRouter:
    router = APIRouter()

    @router.get("/v1/token/{mint}/risk")
    async def token_risk(mint: str) -> dict:
        try:
            mint = parse_address(mint)
        except InvalidAddress:
            raise HTTPException(status_code=400, detail="That is not a valid Solana token address.") from None
        if checker is None:
            raise HTTPException(status_code=503, detail="Token checks are not available right now.")
        try:
            return await checker.check(mint)
        except NotAToken:
            raise HTTPException(status_code=400, detail="That address is not a token. Paste the token's mint address.") from None

    return router
