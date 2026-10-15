"""Measured 2026-10-15 beta posts and integer post accounting; no local data needed."""
import pytest

from brownstone.deposits import auction_deposit

# Cicelyna journal hook sequence, item, vendor copper, quantity, stack limit, hours, paid copper.
# Bag deltas identify items; PLAYER_MONEY deltas prove paid deposits (4344 at 2h changed no gold).
BETA_POSTS = [
    (4439, 4344, 11, 1, 1, 2, 0),
    (4442, 4344, 11, 1, 1, 8, 2),
    (4446, 4344, 11, 1, 1, 24, 6),
    (4458, 2589, 13, 1, 20, 2, 100),
    (4462, 2589, 13, 1, 20, 8, 100),
    (4466, 2589, 13, 1, 20, 24, 100),
    (4472, 2996, 40, 5, 20, 8, 100),
    (4478, 2996, 40, 5, 20, 24, 120),
    (4482, 2996, 40, 4, 20, 2, 100),
    (4486, 2672, 4, 4, 20, 24, 100),
    (5191, 2318, 15, 1, 20, 24, 100),
    (5195, 2318, 15, 1, 20, 24, 100),
    (5199, 765, 10, 2, 20, 24, 100),
]


@pytest.mark.parametrize('sequence,item,vendor,quantity,stack,hours,paid', BETA_POSTS)
def test_beta_posts(sequence, item, vendor, quantity, stack, hours, paid):
    assert auction_deposit(vendor, quantity, stack, hours, 'alliance') == paid


def test_round_per_item_before_summing_and_no_item_minimum():
    assert auction_deposit(11, 5, 1, 24, 'horde') == 30
    assert auction_deposit(11, 5, 1, 2, 'alliance') == 0
    assert auction_deposit(41, 5, 20, 24, 'alliance') == 123
    assert auction_deposit(40, 100, 20, 24, 'alliance') == 2400  # One commodity post.


@pytest.mark.parametrize('vendor,stack,faction', [(None, 20, 'alliance'), (0, 20, 'alliance'),
                                               (40, None, 'alliance'), (40, 0, 'alliance'),
                                               (40, 20, 'neutral')])
def test_unknown(vendor, stack, faction):
    assert auction_deposit(vendor, 5, stack, 24, faction) is None


@pytest.mark.parametrize('hours', [0, 12, True, 2.0])
def test_invalid_duration(hours):
    with pytest.raises(ValueError, match='Post duration'):
        auction_deposit(40, 5, 20, hours, 'alliance')
