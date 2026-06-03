"""Task implementations.

Importing this package registers each task with ``benchmark.registry.TASKS``
as a side-effect. To make a new task discoverable, import its module here.
"""

from benchmark.tasks import sglb_04  # noqa: F401  (registration side-effect)
from benchmark.tasks import sglb_11  # noqa: F401  (registration side-effect)

__all__ = ["sglb_04", "sglb_11"]
