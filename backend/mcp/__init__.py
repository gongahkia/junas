# junas mcp server package. import lazily to avoid runpy double-import warning when
# server.py is invoked as a module (python -m backend.mcp.server).
__all__ = ["server"]

def __getattr__(name):  # noqa: D401 — pep 562 module getattr
    if name == "server":
        from .server import server as _s
        return _s
    raise AttributeError(name)
