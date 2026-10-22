import hashlib
import unittest

from junas.backend.auth import TenantContext
from junas.helper.tenant_storage import tenant_storage_name


class TenantStorageNameTests(unittest.TestCase):
    def test_distinct_authoritative_ids_stay_distinct_on_case_insensitive_filesystems(self):
        ids = [
            "tenant/a",
            "tenant?a",
            "tenant_a",
            "Tenant_a",
            "tenant_a.",
            "tenant_a ",
            "租户甲",
            "租户乙",
            "a" * 128 + "x",
            "a" * 128 + "y",
            "con",
            "CON",
            "~" + hashlib.sha256(b"tenant/a").hexdigest(),
        ]
        names = [tenant_storage_name(identity) for identity in ids]
        self.assertEqual(len({name.casefold().rstrip(" .") for name in names}), len(ids))
        self.assertTrue(all("/" not in name and "\\" not in name and len(name) <= 128 for name in names))
        self.assertEqual(tenant_storage_name("tenant-a"), "tenant-a")

    def test_authenticated_context_keeps_exact_identity_until_the_storage_boundary(self):
        for identity in ["tenant/a", "tenant_a", "Tenant_a", "租户甲"]:
            context = TenantContext(
                tenant_id=identity,
                subject="synthetic",
                roles=frozenset({"reviewer"}),
                auth_mode="api_key",
                enabled=True,
            )
            self.assertEqual(context.storage_tenant_id, identity)
