"""Pure state transitions; versioned 2026/27 rules, never FPL write requests."""
from dataclasses import dataclass

CHIPS = frozenset(('wildcard', 'freehit', 'bboost', '3xc'))


def selling_price(purchase, market):
    if type(purchase) is not int or type(market) is not int or min(purchase, market) < 0:
        raise ValueError('Prices must be nonnegative integer tenths')
    return market if market <= purchase else purchase + (market - purchase) // 2


def next_ft(ft, transfers, chip=None):
    if type(ft) is not int or not 0 <= ft <= 5 or type(transfers) is not int or transfers < 0:
        raise ValueError('Invalid transfer state')
    if chip not in CHIPS | {None}:
        raise ValueError('Unknown chip')
    # Saved FTs retained, but no additional FT earned on WC/FH weeks.
    return ft if chip in ('wildcard', 'freehit') else min(5, max(0, ft - transfers) + 1)


def chip_allowed(gw, chip, used):
    """used is a tuple of (GW, chip); first-half inventory expires at GW19."""
    if not 1 <= gw <= 38 or chip not in CHIPS | {None}:
        return False
    if chip is None:
        return True
    half = lambda w: 1 if w <= 19 else 2
    if any(w == gw or (c == chip and half(w) == half(gw)) for w, c in used):
        return False
    return not (chip in ('freehit', 'wildcard') and gw == 1 or
                chip == 'freehit' and any(c == 'freehit' and w == gw-1 for w, c in used))


@dataclass(frozen=True)
class State:
    # holdings: (player ID, purchase price). Current selling prices are computed
    # against each GW's explicit market-price scenario, never reconstructed publicly.
    holdings: tuple
    bank: int
    ft: int
    used: tuple = ()
