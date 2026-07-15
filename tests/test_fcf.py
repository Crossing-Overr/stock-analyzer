import math
from core.data import normalize_fcf
from core.dcf import dcf_upside_base


# ─── normalize_fcf: медиана последних N годовых FCF ──────────────────────────
def test_median_of_recent_window_ignores_older_outlier():
    # AMZN: newest-first [7.7, 32.9, 32.2, -16.9] → окно 3 → median(7.7,32.9,32.2)=32.2
    assert normalize_fcf([7.7, 32.9, 32.2, -16.9], window=3) == 32.2

def test_all_negative_returns_negative_median():
    # INTC: все годы отрицательные → median последних 3 отрицательна
    assert normalize_fcf([-4.9, -15.7, -14.3, -9.4], window=3) == -14.3

def test_empty_falls_back_to_trailing():
    assert normalize_fcf([], trailing=5.0) == 5.0

def test_none_input_falls_back_to_trailing():
    assert normalize_fcf(None, trailing=None) is None

def test_nan_values_are_filtered():
    assert normalize_fcf([float("nan"), 10.0, 20.0], window=3) == 15.0

def test_single_value():
    assert normalize_fcf([100.0]) == 100.0


# ─── dcf_upside_base: апсайд Base-сценария или None при непригодности ─────────
def test_upside_none_for_negative_fcf():
    assert dcf_upside_base(fcf_base=-5e9, price=50, shares=10, net_debt=0,
                           growth_rates={"bear": 0, "base": 0.08, "bull": 0.15},
                           wacc=0.10, terminal_growth=0.025, years=5) is None

def test_upside_none_for_zero_shares_or_price():
    common = dict(growth_rates={"bear": 0, "base": 0, "bull": 0},
                  wacc=0.10, terminal_growth=0.0, years=1)
    assert dcf_upside_base(fcf_base=100, price=50, shares=0, net_debt=0, **common) is None
    assert dcf_upside_base(fcf_base=100, price=0, shares=10, net_debt=0, **common) is None

def test_upside_positive_when_intrinsic_above_price():
    # golden: fcf 100, wacc .1, term 0, yr1, shares 10 → intrinsic 100; price 50 → +100%
    up = dcf_upside_base(fcf_base=100, price=50, shares=10, net_debt=0,
                         growth_rates={"bear": 0, "base": 0, "bull": 0},
                         wacc=0.10, terminal_growth=0.0, years=1)
    assert math.isclose(up, 100.0, rel_tol=1e-9)
