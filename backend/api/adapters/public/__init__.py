"""Public, free-tier SG legal source adapters.

All adapters here MUST be ``AdapterTier.PUBLIC`` and benchmark-eligible.
Each module is a stub at scaffold time; real fetchers live in #27, #28,
#34, #59, #60 implementations and slot into these stubs.
"""

from api.adapters.public.austlii_sg import AustliiSgAdapter
from api.adapters.public.commonlii_sg import CommonliiSgAdapter
from api.adapters.public.elitigation import ElitigationAdapter
from api.adapters.public.hansard import HansardAdapter
from api.adapters.public.iras import IrasAdapter
from api.adapters.public.mom import MomAdapter
from api.adapters.public.pdpc import PdpcAdapter
from api.adapters.public.pdpc_guidance import PdpcGuidanceAdapter
from api.adapters.public.sso import SsoAdapter

__all__ = [
    "AustliiSgAdapter",
    "CommonliiSgAdapter",
    "ElitigationAdapter",
    "HansardAdapter",
    "IrasAdapter",
    "MomAdapter",
    "PdpcAdapter",
    "PdpcGuidanceAdapter",
    "SsoAdapter",
]
