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

    # rate limits (per remote IP)
    rl_create_session_per_min: int = 10
    rl_join_per_min: int = 30
    rl_climbs_per_min: int = 60

    # sweeper
    session_idle_max_hours: int = 24  # end sessions with no activity for this long
    sweep_interval_seconds: int = 300  # how often the sweeper runs

    # auth
    auth_access_ttl_seconds: int = 3600
    auth_refresh_ttl_seconds: int = 30 * 24 * 3600
    auth_magic_link_ttl_seconds: int = 900
    # when true, POST /auth/magic-link returns the token in the response body.
    # production deployments should set this to false and plug in an email sender.
    auth_return_magic_links: bool = True

    # boards directory
    boards_autoload_sample: bool = True
