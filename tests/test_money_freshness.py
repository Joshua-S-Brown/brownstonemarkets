from datetime import datetime, timedelta, timezone

import pytest

from brownstone.freshness import assess, is_stale
from brownstone.money import format_money, to_gold

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


@pytest.mark.parametrize("copper,text", [
    (0, "0c"), (7, "7c"), (1800, "18s"), (45097, "4g 50s 97c"), (10000, "1g"),
    (-1582, "-15s 82c"), (12_345_678, "1,234g 56s 78c"), (None, "—"),
])
def test_format_money(copper, text):
    assert format_money(copper) == text


def test_gold_is_exact_to_one_copper():
    assert to_gold(1) == 0.0001
    assert to_gold(None) is None


def test_freshness_prefers_upstream_and_labels_collection_fallback():
    upstream = assess({"updated_at": (NOW - timedelta(hours=30)).isoformat(),
                       "collected_at": NOW.isoformat()}, NOW, 24)
    assert upstream["basis"] == "upstream scan" and upstream["stale"]
    collection = assess({"updated_at": None, "collected_at": NOW.isoformat()}, NOW, 24)
    assert collection["basis"] == "collection" and not collection["upstream_known"]


def test_staleness_boundaries():
    assert not is_stale(24, 24) and is_stale(24.001, 24)
    assert not is_stale(-0.25, 24) and is_stale(-0.26, 24)
    with pytest.raises(ValueError):
        is_stale(1, 0)
