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
    rl_backend: str = "in_memory"
    rl_redis_url: str = ""
    rl_redis_prefix: str = "kt:rl"
    rl_redis_ttl_seconds: int = 300
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
    boards_source_mode: str = "sample"  # sample | remote | auto
    boards_source_name: str = "hangtime_climbing_boards"
    boards_source_url: str = ""
    boards_sync_enabled: bool = False
    boards_sync_interval_seconds: int = 21_600
    boards_sync_timeout_seconds: int = 30
