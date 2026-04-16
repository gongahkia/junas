from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KT_", env_file=".env", extra="ignore")

    db_path: Path = Path("./data/kt.db")
    cred_key: str = ""  # overridden in env; required for credential storage
    log_level: str = "info"

    session_code_len: int = 6
    cache_ttl_seconds: int = 86_400

    # rate limits (per remote IP)
    rl_create_session_per_min: int = 10
    rl_get_session_per_min: int = 120
    rl_attach_credentials_per_min: int = 30
    rl_end_session_per_min: int = 30
    rl_climbs_per_min: int = 60
    rl_layouts_per_min: int = 60
    rl_boards_reload_per_min: int = 10

    # sweeper
    session_idle_max_hours: int = 24  # end sessions with no activity for this long
    sweep_interval_seconds: int = 300  # how often the sweeper runs

    # boards directory
    boards_autoload_sample: bool = True
    boards_reload_secret: str = ""
