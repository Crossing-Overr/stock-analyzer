import math
from core.dcf import run_dcf
from core.dcf_analysis import implied_growth

PARAMS = dict(fcf_base=100.0, shares=10.0, net_debt=0.0,
              wacc=0.10, terminal_growth=0.025, years=5)


def _fair_price(growth, wacc=0.10, terminal_growth=0.025, years=5,
                fcf_base=100.0, shares=10.0, net_debt=0.0):
    """Справедливая цена при известном росте — эталон для round-trip."""
    return run_dcf(fcf_base=fcf_base, growth_rates={"base": growth}, wacc=wacc,
                   terminal_growth=terminal_growth, years=years,
                   shares=shares, net_debt=net_debt)["base"].intrinsic


def test_implied_growth_roundtrip():
    # Золотой тест: цена, посчитанная при росте 8%, должна дать обратно ≈8%
    fair = _fair_price(0.08)
    g = implied_growth(price=fair, **PARAMS)
    assert g is not None
    assert math.isclose(g, 0.08, abs_tol=1e-4)


def test_implied_growth_roundtrip_negative_growth():
    fair = _fair_price(-0.05)
    g = implied_growth(price=fair, **PARAMS)
    assert math.isclose(g, -0.05, abs_tol=1e-4)


def test_implied_growth_higher_price_implies_higher_growth():
    low = implied_growth(price=_fair_price(0.05), **PARAMS)
    high = implied_growth(price=_fair_price(0.20), **PARAMS)
    assert high > low


def test_implied_growth_none_for_negative_fcf():
    p = {**PARAMS, "fcf_base": -5.0}
    assert implied_growth(price=100.0, **p) is None


def test_implied_growth_none_for_zero_shares_or_price():
    assert implied_growth(price=100.0, **{**PARAMS, "shares": 0.0}) is None
    assert implied_growth(price=0.0, **PARAMS) is None


def test_implied_growth_none_when_out_of_range():
    # Абсурдно высокая цена — даже рост +100% её не оправдывает
    assert implied_growth(price=1e9, **PARAMS) is None
