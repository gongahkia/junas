"""Backward-compatible import path for the extracted ``sglb_tools`` package."""

try:
    from sglb_tools.citation import *  # noqa: F403
    from sglb_tools.citation import __all__  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "sglb_tools":
        raise
    import sys
    from pathlib import Path

    package_root = Path(__file__).resolve().parents[3] / "packages" / "sglb-tools"
    sys.path.insert(0, str(package_root))
    from sglb_tools.citation import *  # noqa: F403,E402
    from sglb_tools.citation import __all__  # noqa: E402,F401
