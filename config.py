import os
try:
    import tomllib
except ImportError:
    import tomli as tomllib

CONFIG_PATH = os.environ.get("NOUPE_CONFIG", os.path.join(os.path.dirname(__file__), "config.toml"))

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "rb") as f:
            try:
                return tomllib.load(f)
            except Exception:
                pass
    return {}

_cfg = load_config()

def get_config_val(section, key, env_var, default, cast_type=str):
    val = os.getenv(env_var)
    if val is not None:
        return cast_type(val)
    sec = _cfg.get(section, {})
    if key in sec:
        return cast_type(sec[key])
    return cast_type(default)
