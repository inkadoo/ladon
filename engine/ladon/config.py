import os
import secrets
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    helius_api_key: str | None = None
    database_url: str | None = None
    reporter_salt: str = field(default_factory=lambda: secrets.token_hex(32))
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)


def load_settings() -> Settings:
    origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
    return Settings(
        helius_api_key=os.environ.get("HELIUS_API_KEY") or None,
        database_url=os.environ.get("DATABASE_URL") or None,
        reporter_salt=os.environ.get("REPORTER_SALT") or secrets.token_hex(32),
        allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
    )
