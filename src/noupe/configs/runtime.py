import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = os.environ.get("NOUPE_CONFIG", str(PROJECT_ROOT / "config.toml"))

def load_config() -> dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "rb") as f:
            try:
                return tomllib.load(f)
            except Exception:
                pass
    return {}

_cfg = load_config()

def get_config_val(
    section: str,
    key: str,
    env_var: str,
    default: Any,
    cast_type: Any = str,
) -> Any:
    val = os.getenv(env_var)
    if val is not None:
        return cast_type(val)
    sec = _cfg.get(section, {})
    if key in sec:
        return cast_type(sec[key])
    return cast_type(default)
