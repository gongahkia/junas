import pytest

from kt.providers.base import ClimbQuery, ProviderStatus, ProviderUnavailable
from kt.providers.kilter.provider import KilterProvider


def test_marked_experimental():
    p = KilterProvider()
    assert p.status is ProviderStatus.EXPERIMENTAL
    assert p.requires_credentials


async def test_calls_raise_unavailable_until_upstream_ready():
    p = KilterProvider()
    with pytest.raises(ProviderUnavailable):
        await p.list_layouts(None)
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(None, ClimbQuery())
    with pytest.raises(ProviderUnavailable):
        await p.get_climb(None, "x")


async def test_authenticate_propagates_client_unavailable():
    p = KilterProvider()
    with pytest.raises(ProviderUnavailable):
        await p.authenticate({"username": "u", "password": "p"})
