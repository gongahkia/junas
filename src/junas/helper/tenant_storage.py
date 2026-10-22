"""Keep exact tenant identity distinct from a filesystem component."""

import hashlib
import re


def tenant_storage_name(tenant_id: str) -> str:
    # Preserve existing ordinary lowercase tenant paths. Case-only differences
    # must remain distinct on macOS/Windows filesystems too. The '~' namespace cannot be
    # produced by a safe literal ID, including one resembling another ID's hash.
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    if (
        re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,127}", tenant_id)
        and not tenant_id.endswith(".")
        and tenant_id.split(".")[0] not in reserved
    ):
        return tenant_id
    return "~" + hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
