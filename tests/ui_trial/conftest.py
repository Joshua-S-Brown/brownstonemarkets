"""Use NiceGUI's user fixture locally, with explicit asyncio mode and no global plugin."""
import pytest_asyncio
from nicegui.testing.user_plugin import user as nicegui_user

user = pytest_asyncio.fixture(nicegui_user.__wrapped__)
