import os
import secrets
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    helius_api_key: str | None = None
    database_url: str | None = None
    reporter_salt: str = field(default_factory=lambda: secrets.token_hex(32))
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)
    x_client_id: str = ""
    x_client_secret: str = ""
    x_redirect_uri: str = "https://getladon.vercel.app/airdrop"
    airdrop_encryption_key: str = ""


def load_settings() -> Settings:
    origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
    return Settings(
        helius_api_key=os.environ.get("HELIUS_API_KEY") or None,
        database_url=os.environ.get("DATABASE_URL") or None,
        reporter_salt=os.environ.get("REPORTER_SALT") or secrets.token_hex(32),
        allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        x_client_id=os.environ.get("X_CLIENT_ID", ""),
        x_client_secret=os.environ.get("X_CLIENT_SECRET", ""),
        x_redirect_uri=os.environ.get("X_REDIRECT_URI", "https://getladon.vercel.app/airdrop"),
        airdrop_encryption_key=os.environ.get("AIRDROP_ENCRYPTION_KEY", ""),
    )
