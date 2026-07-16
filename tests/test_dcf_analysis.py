import math
from core.dcf import run_dcf
from core.dcf_analysis import implied_growth, implied_return, sensitivity_grid

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


def test_implied_return_roundtrip():
    # Цена, посчитанная при WACC 12%, должна дать обратно ≈12%
    fair = _fair_price(0.08, wacc=0.12)
    r = implied_return(price=fair, fcf_base=100.0, shares=10.0, net_debt=0.0,
                       growth_start=0.08, terminal_growth=0.025, years=5)
    assert r is not None
    assert math.isclose(r, 0.12, abs_tol=1e-4)


def test_implied_return_lower_price_means_higher_return():
    common = dict(fcf_base=100.0, shares=10.0, net_debt=0.0,
                  growth_start=0.08, terminal_growth=0.025, years=5)
    cheap = implied_return(price=_fair_price(0.08, wacc=0.15), **common)
    rich = implied_return(price=_fair_price(0.08, wacc=0.07), **common)
    assert cheap > rich   # дешевле купил → больше заработал


def test_implied_return_none_for_negative_fcf():
    assert implied_return(price=100.0, fcf_base=-5.0, shares=10.0, net_debt=0.0,
                          growth_start=0.08, terminal_growth=0.025, years=5) is None


def test_implied_return_none_when_out_of_range():
    # Абсурдно высокая цена — не оправдывается даже минимальной ставкой
    assert implied_return(price=1e12, fcf_base=100.0, shares=10.0, net_debt=0.0,
                          growth_start=0.08, terminal_growth=0.025, years=5) is None


GRID_ARGS = dict(fcf_base=100.0, price=50.0, shares=10.0, net_debt=0.0,
                 growth_start=0.08, years=5)


def test_grid_is_5x5():
    g = sensitivity_grid(wacc=0.10, terminal_growth=0.025, **GRID_ARGS)
    assert len(g.waccs) == 5
    assert len(g.terminal_growths) == 5
    assert len(g.cells) == 5
    assert all(len(row) == 5 for row in g.cells)


def test_grid_centered_on_current_params():
    g = sensitivity_grid(wacc=0.10, terminal_growth=0.025, **GRID_ARGS)
    assert math.isclose(g.waccs[2], 0.10, abs_tol=1e-9)          # центр по WACC
    assert math.isclose(g.terminal_growths[2], 0.025, abs_tol=1e-9)
    assert math.isclose(g.waccs[0], 0.08, abs_tol=1e-9)          # ±2 п.п. шагом 1
    assert math.isclose(g.waccs[4], 0.12, abs_tol=1e-9)
    assert math.isclose(g.terminal_growths[0], 0.015, abs_tol=1e-9)  # ±1 п.п. шагом 0.5
    assert math.isclose(g.terminal_growths[4], 0.035, abs_tol=1e-9)


def test_center_cell_matches_plain_dcf_and_is_marked_current():
    g = sensitivity_grid(wacc=0.10, terminal_growth=0.025, **GRID_ARGS)
    center = g.cells[2][2]
    assert center.is_current is True
    expected = _fair_price(0.08, wacc=0.10, terminal_growth=0.025)
    assert math.isclose(center.intrinsic, expected, rel_tol=1e-9)
    assert math.isclose(center.upside, (expected - 50.0) / 50.0 * 100, rel_tol=1e-9)


def test_only_center_is_marked_current():
    g = sensitivity_grid(wacc=0.10, terminal_growth=0.025, **GRID_ARGS)
    marked = [c for row in g.cells for c in row if c.is_current]
    assert len(marked) == 1


def test_cells_where_terminal_ge_wacc_are_empty():
    # WACC 5%, терм. рост 4.5% → часть сетки уходит в зону terminal >= wacc
    g = sensitivity_grid(wacc=0.05, terminal_growth=0.045, **GRID_ARGS)
    empty = [c for row in g.cells for c in row if c.intrinsic is None]
    assert empty, "ожидались пустые ячейки там, где терм. рост >= WACC"
    for c in empty:
        assert c.terminal_growth >= c.wacc
        assert c.upside is None


def test_normal_grid_has_no_empty_cells():
    g = sensitivity_grid(wacc=0.10, terminal_growth=0.025, **GRID_ARGS)
    assert all(c.intrinsic is not None for row in g.cells for c in row)


def test_grid_none_for_negative_fcf():
    args = {**GRID_ARGS, "fcf_base": -5.0}
    assert sensitivity_grid(wacc=0.10, terminal_growth=0.025, **args) is None
