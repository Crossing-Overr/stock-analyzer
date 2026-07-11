import math
from core.dcf import run_dcf, ScenarioResult

BASE = dict(
    fcf_base=100.0,
    wacc=0.10,
    terminal_growth=0.0,
    years=1,
    shares=10.0,
    net_debt=0.0,
)

def test_golden_single_year_zero_growth():
    # y1: fcf=100, pv=100/1.1=90.909; TV=100/(0.1-0)=1000, pv_tv=1000/1.1=909.09
    # EV=1000, equity=1000, intrinsic=100, tv_share=0.9090909
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.0, "bull": 0.0}, **BASE)
    r = res["base"]
    assert isinstance(r, ScenarioResult)
    assert math.isclose(r.enterprise_value, 1000.0, rel_tol=1e-9)
    assert math.isclose(r.intrinsic, 100.0, rel_tol=1e-9)
    assert math.isclose(r.tv_share, 909.0909090909091 / 1000.0, rel_tol=1e-9)

def test_net_debt_reduces_equity():
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.0, "bull": 0.0},
                  **{**BASE, "net_debt": 200.0})
    assert math.isclose(res["base"].intrinsic, 80.0, rel_tol=1e-9)

def test_higher_growth_gives_higher_value():
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.08, "bull": 0.20},
                  **{**BASE, "years": 5})
    assert res["bull"].intrinsic > res["base"].intrinsic > res["bear"].intrinsic

def test_growth_fades_to_terminal():
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.20, "bull": 0.0},
                  **{**BASE, "years": 5, "terminal_growth": 0.02})
    path = res["base"].growth_path
    assert math.isclose(path[0], 0.20, rel_tol=1e-9)      # 1-й год = стартовый
    assert math.isclose(path[-1], 0.02, rel_tol=1e-9)     # последний = терминальный
    assert len(path) == 5

def test_wacc_not_greater_than_terminal_is_guarded():
    # wacc == terminal → без защиты деление на ноль; ждём конечное число
    res = run_dcf(growth_rates={"bear": 0.05, "base": 0.05, "bull": 0.05},
                  **{**BASE, "wacc": 0.05, "terminal_growth": 0.05, "years": 3})
    assert math.isfinite(res["base"].intrinsic)

def test_zero_shares_gives_zero_intrinsic():
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.0, "bull": 0.0},
                  **{**BASE, "shares": 0.0})
    assert res["base"].intrinsic == 0.0
