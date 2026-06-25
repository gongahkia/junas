import os
import random
import sys
from typing import Optional

import numpy as np


def configure_determinism(seed: Optional[int] = None, deterministic: Optional[bool] = None) -> dict:
    """
    Configure process-level determinism controls.

    Environment controls:
    - KAYPOH_SEED (default: 42)
    - KAYPOH_DETERMINISTIC (1/true/on enables deterministic backend behavior)
    - KAYPOH_CONFIGURE_TORCH_DETERMINISM (1/true/on opt-in for Torch setup)
    """
    resolved_seed = int(seed if seed is not None else os.getenv("KAYPOH_SEED", "42"))
    if deterministic is None:
        deterministic = os.getenv("KAYPOH_DETERMINISTIC", "0").lower() in {"1", "true", "on", "yes"}

    # Best-effort; PYTHONHASHSEED should ideally be set before interpreter startup.
    os.environ.setdefault("PYTHONHASHSEED", str(resolved_seed))
    random.seed(resolved_seed)
    np.random.seed(resolved_seed)

    # Torch is server/training-only. Importing it opportunistically can crash local
    # Python environments before an exception is catchable, so configure it only
    # when the caller explicitly opts in or has already imported torch.
    torch_ready = False
    configure_torch = os.getenv("KAYPOH_CONFIGURE_TORCH_DETERMINISM", "0").lower() in {
        "1",
        "true",
        "on",
        "yes",
    }
    if configure_torch or "torch" in sys.modules:
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
