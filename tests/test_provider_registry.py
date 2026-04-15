from kt.providers import registry
from kt.providers.base import (
    AuthToken,
    BoardProvider,
    Climb,
    ClimbQuery,
    Layout,
    ProviderStatus,
)


class FakeProvider:
    key = "fake"
    name = "Fake"
    status = ProviderStatus.OK
    requires_credentials = False

    async def authenticate(self, creds):
        return AuthToken(provider=self.key, value="t")

    async def list_layouts(self, token):
        return [Layout(id="1", name="L")]

    async def search_climbs(self, token, query: ClimbQuery):
        return []

    async def get_climb(self, token, climb_id):
        return Climb(
            id=climb_id,
            provider=self.key,
            name="x",
            setter=None,
            grade=None,
            angle=None,
            ascents=None,
        )


def test_register_and_get():
    registry.reset()
    p: BoardProvider = FakeProvider()
    registry.register(p)
    assert registry.get("fake") is p
    assert registry.describe() == [
        {"key": "fake", "name": "Fake", "status": "ok", "requires_credentials": False}
    ]


def test_get_unknown():
    registry.reset()
    try:
        registry.get("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")
