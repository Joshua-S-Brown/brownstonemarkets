"""Surviving Data dialog checks; Today dialog tests moved to Today Vitest/API suites."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_data_info_dialog_and_status_chips(user, tmp_path, monkeypatch):
    from app_helpers import preview_addon

    _, source = preview_addon(tmp_path, monkeypatch)
    await user.open('/?place=Data')
    await user.should_see('Check for new scans')
    await user.should_see('scans imported')
    await user.should_see('Drop folder')
    await user.should_not_see(f"source_id: {source['source_id']}")
    user.find(marker='page-info').click()
    await user.should_see(f"source_id: {source['source_id']}")
    await user.should_see('Partial scans are preserved but never feed prices')
