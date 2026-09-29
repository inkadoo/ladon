import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import asyncpg
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException, Request

from .addresses import InvalidAddress, b58decode


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def bearer(request: Request) -> str:
    value = request.headers.get("authorization", "")
    if not value.startswith("Bearer ") or not 20 < len(value) < 150:
        raise HTTPException(401, "Connect your wallet and sign in first.")
    return value[7:]


class AirdropAuth:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def limit(self, key: str, maximum: int = 30) -> None:
        count = await self.pool.fetchval(
            "insert into airdrop_limits (key, bucket) values ($1, date_trunc('minute', now())) "
            "on conflict (key, bucket) do update set count = airdrop_limits.count + 1 returning count", key,
        )
        if count > maximum:
            raise HTTPException(429, "Too many requests. Please wait a minute.")

    async def challenge(self, wallet: str, origin: str) -> dict:
        nonce = secrets.token_hex(24)
        now = datetime.now(UTC)
        expires = now + timedelta(minutes=5)
        message = (
            f"{urlsplit(origin).netloc} wants you to sign in with your Solana account:\n{wallet}\n\n"
            "Sign in to Ladon Season 1 and secure your points account. "
            "This message does not authorize transactions or access to your funds.\n\n"
            f"URI: {origin}/airdrop\nVersion: 1\nChain ID: solana:mainnet\nNonce: {nonce}\n"
            f"Issued At: {now.isoformat()}\nExpiration Time: {expires.isoformat()}"
        )
        async with self.pool.acquire() as conn, conn.transaction():
            await conn.execute("delete from airdrop_challenges where expires_at < now()")
            await conn.execute("delete from airdrop_sessions where expires_at < now()")
            await conn.execute("update airdrop_x_accounts set access_token = null where expires_at < now() and access_token is not null")
            await conn.execute("delete from airdrop_limits where bucket < now() - interval '1 day'")
            await conn.execute("insert into airdrop_challenges values ($1, $2, $3, $4)", nonce, wallet, message, expires)
        return {"nonce": nonce, "message": message}

    async def verify(self, wallet: str, nonce: str, signature: str) -> dict:
        async with self.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "select message from airdrop_challenges where nonce = $1 and wallet = $2 and expires_at > now() for update",
                nonce, wallet,
            )
            if not row:
                raise HTTPException(401, "This sign-in request expired or was already used. Connect again.")
            try:
                signature_bytes = b58decode(signature)
                if len(signature_bytes) != 64:
                    raise ValueError("signature length")
                Ed25519PublicKey.from_public_bytes(b58decode(wallet)).verify(signature_bytes, row["message"].encode())
            except (InvalidSignature, InvalidAddress, ValueError):
                raise HTTPException(401, "The wallet signature could not be verified.") from None
            await conn.execute("delete from airdrop_challenges where nonce = $1", nonce)
            token = secrets.token_urlsafe(32)
            expires = datetime.now(UTC) + timedelta(hours=12)
            await conn.execute("insert into airdrop_sessions values ($1, $2, $3)", digest(token), wallet, expires)
            return {"token": token, "wallet": wallet, "expires_at": expires.isoformat()}

    async def wallet(self, token: str) -> str:
        wallet = await self.pool.fetchval(
            "select wallet from airdrop_sessions where token_hash = $1 and expires_at > now()", digest(token),
        )
        if not wallet:
            raise HTTPException(401, "Your sign-in has expired. Connect your wallet again.")
        return wallet

    async def require_wallet(self, wallet: str, request: Request) -> None:
        if await self.wallet(bearer(request)) != wallet:
            raise HTTPException(403, "This session belongs to a different wallet.")
