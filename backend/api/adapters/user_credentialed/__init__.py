"""User-credentialed (paid-source) legal adapters — Phase 3 only.

Adapters here are excluded from benchmark dataset construction by tier.
They may only be used by the copilot, and only when the end user has
opted in via Settings and supplied credentials that the server does not
persist (OS keychain on desktop; session-only on web).

Hard rules for any adapter added here:

1. **Must use the source's official API**, never session-cookie scraping
   of a logged-in user account.
2. **Server never persists user credentials.** All credentials are
   request-scoped or live in the user's keychain.
3. **Audit-logged user responsibility.** The UI surfaces a notice that
   the user is accessing the paid source under their own subscription
   and is responsible for compliance with the source's terms.
4. **Excluded from benchmark.** ``benchmark_safe_adapters()`` in
   ``api.adapters.base`` filters these out by tier.

No implementations exist at v0.2 scaffold time. The stubs below document
where they would slot in.
"""

from api.adapters.user_credentialed.lawnet import LawnetAdapter
from api.adapters.user_credentialed.lexisnexis_sg import LexisNexisSgAdapter
from api.adapters.user_credentialed.practical_law_sg import PracticalLawSgAdapter

__all__ = [
    "LawnetAdapter",
    "LexisNexisSgAdapter",
    "PracticalLawSgAdapter",
]
