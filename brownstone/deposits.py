"""Auction deposits from scan evidence, in integer copper (Today requirements)."""


def auction_deposit(vendor: int | None, quantity: int, max_stack_size: int | None,
                    hours: int, faction: str) -> int | None:
    """One commodity post, or quantity separate item posts; neutral is unmeasured."""
    if type(hours) is not int or hours not in (2, 8, 24):
        raise ValueError('Post duration must be 2, 8 or 24 hours')
    if vendor is None or vendor <= 0 or max_stack_size is None or max_stack_size <= 0 or faction == 'neutral':
        return None
    if max_stack_size == 1:
        return (vendor * hours // 40) * quantity
    return max(100, vendor * quantity * hours // 40)
