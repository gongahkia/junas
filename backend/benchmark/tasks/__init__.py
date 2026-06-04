"""Task implementations.

Importing this package registers each task with ``benchmark.registry.TASKS``
as a side-effect. To make a new task discoverable, import its module here.
"""

from benchmark.tasks import sglb_01  # noqa: F401  (registration side-effect)
from benchmark.tasks import sglb_02  # noqa: F401  (registration side-effect)
from benchmark.tasks import sglb_04  # noqa: F401  (registration side-effect)
from benchmark.tasks import sglb_08  # noqa: F401  (registration side-effect)
from benchmark.tasks import sglb_11  # noqa: F401  (registration side-effect)
from benchmark.tasks import sglb_12  # noqa: F401  (registration side-effect)
from benchmark.tasks import sglb_15  # noqa: F401  (registration side-effect)

__all__ = ["sglb_01", "sglb_02", "sglb_04", "sglb_08", "sglb_11", "sglb_12", "sglb_15"]
