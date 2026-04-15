from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KT_", env_file=".env", extra="ignore")

    db_path: Path = Path("./data/kt.db")
    cred_key: str = ""  # overridden in env; required for credential storage
    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 8000

    session_code_len: int = 6
    ws_token_ttl_seconds: int = 600
    cache_ttl_seconds: int = 86_400
