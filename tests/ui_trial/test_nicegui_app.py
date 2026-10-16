"""Every legacy place redirects to the web app with its selected source."""

import pytest
from app_helpers import app

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("place", "destination"),
    [
        ("Stock", "/app/ledger?source=test"),
        ("Data", "/app/today?source=test&sheet=data"),
        ("", "/app/today?source=test&view=route"),
    ],
)
async def test_places_redirect_with_source(user, tmp_path, monkeypatch, place, destination):
    _, source, _ = app(tmp_path, monkeypatch)
    monkeypatch.setattr("brownstone.config.read_sources", lambda *args: [source, source | {"source_id": "other"}])
    targets = []
    monkeypatch.setattr(user.navigate, "to", targets.append)
    await user.open("/?game=classic&source=test" + ("&place=" + place if place else ""))
    assert targets[-1] == destination
