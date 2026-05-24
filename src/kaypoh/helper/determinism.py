import os
import random
from typing import Optional

import numpy as np


def configure_determinism(seed: Optional[int] = None, deterministic: Optional[bool] = None) -> dict:
    """
    Configure process-level determinism controls.

    Environment controls:
    - KAYPOH_SEED (default: 42)
    - KAYPOH_DETERMINISTIC (1/true/on enables deterministic backend behavior)
    """
    resolved_seed = int(seed if seed is not None else os.getenv("KAYPOH_SEED", "42"))
    if deterministic is None:
        deterministic = os.getenv("KAYPOH_DETERMINISTIC", "0").lower() in {"1", "true", "on", "yes"}

    # Best-effort; PYTHONHASHSEED should ideally be set before interpreter startup.
    os.environ.setdefault("PYTHONHASHSEED", str(resolved_seed))
    random.seed(resolved_seed)
    np.random.seed(resolved_seed)

    torch_ready = False
    try:
        import torch

        torch.manual_seed(resolved_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(resolved_seed)
        if deterministic:
            torch.use_deterministic_algorithms(True, warn_only=True)
            if hasattr(torch.backends, "cudnn"):
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False
        torch_ready = True
    except Exception:
        torch_ready = False

    return {
        "seed": resolved_seed,
        "deterministic": bool(deterministic),
        "torch_configured": torch_ready,
    }

