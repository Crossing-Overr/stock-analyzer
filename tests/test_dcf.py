import math
from core.dcf import run_dcf, ScenarioResult, dcf_upside_base

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


def test_terminal_multiple_replaces_gordon():
    """Терминал = FCF последнего года × мультипликатор, ровно."""
    # fcf 100, рост 0 (старт = терминальный), 1 год → FCF_1 = 100
    res = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                  terminal_growth=0.0, years=1, shares=10.0, net_debt=0.0,
                  terminal_multiple=15.0)
    r = res["base"]
    # TV = 100 * 15 = 1500; приведённая = 1500/1.1
    assert math.isclose(r.pv_terminal, 1500.0 / 1.1, rel_tol=1e-12)
    # EV = PV(FCF года 1) + PV(TV) = 100/1.1 + 1500/1.1 = 1600/1.1
    assert math.isclose(r.enterprise_value, 1600.0 / 1.1, rel_tol=1e-12)
    assert math.isclose(r.intrinsic, (1600.0 / 1.1) / 10.0, rel_tol=1e-12)


def test_terminal_multiple_ignores_terminal_growth():
    """В режиме мультипликатора терминальный рост на сам терминал не влияет:
    отношение приведённого терминала к приведённому FCF последнего года всегда
    равно мультипликатору."""
    a = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                terminal_growth=0.0, years=5, shares=10.0, net_debt=0.0,
                terminal_multiple=15.0)["base"]
    b = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                terminal_growth=0.04, years=5, shares=10.0, net_debt=0.0,
                terminal_multiple=15.0)["base"]
    assert math.isclose(a.pv_terminal / a.fcfs_pv[-1], 15.0, rel_tol=1e-9)
    assert math.isclose(b.pv_terminal / b.fcfs_pv[-1], 15.0, rel_tol=1e-9)


def test_none_multiple_is_gordon_unchanged():
    """None → поведение ровно как раньше (прежний golden-тест не меняется)."""
    with_none = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                        terminal_growth=0.0, years=1, shares=10.0, net_debt=0.0,
                        terminal_multiple=None)["base"]
    default = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                      terminal_growth=0.0, years=1, shares=10.0, net_debt=0.0)["base"]
    assert math.isclose(with_none.intrinsic, 100.0, rel_tol=1e-9)
    assert math.isclose(with_none.intrinsic, default.intrinsic, rel_tol=1e-12)


def test_non_positive_multiple_falls_back_to_gordon():
    """Мультипликатор ≤ 0 трактуется как «не задан» — иначе терминал отрицательный."""
    fallback = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                       terminal_growth=0.0, years=1, shares=10.0, net_debt=0.0,
                       terminal_multiple=0.0)["base"]
    assert math.isclose(fallback.intrinsic, 100.0, rel_tol=1e-9)


def test_dcf_upside_base_accepts_terminal_multiple():
    """Апсайд в режиме мультипликатора выше, чем по Гордону при тех же входных."""
    common = dict(fcf_base=100.0, price=50.0, shares=10.0, net_debt=0.0,
                  growth_rates={"bear": 0.0, "base": 0.0, "bull": 0.0},
                  wacc=0.10, terminal_growth=0.025, years=10)
    gordon = dcf_upside_base(**common)
    mult = dcf_upside_base(**common, terminal_multiple=25.0)
    assert gordon is not None and mult is not None
    assert mult > gordon        # 25x щедрее, чем Гордон при 10%/2.5% (≈13.7x)
