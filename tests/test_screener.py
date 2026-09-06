from core.screener import screen, ScreenFilters, PRESETS, load_snapshot


def _snapshot():
    """Синтетический снимок, покрывающий каждый пресет + мусор, который обязан
    отсеиваться. rf=0.045."""
    def row(sym, **kw):
        base = dict(symbol=sym, name=sym + " Inc.", sector="Tech", price=100.0,
                    market_cap=1e11, pe=20.0, fcf_base=5e9, fcf_positive=True,
                    fcf_multiple=15.0, wacc=0.10, upside_base=10.0,
                    implied_growth=0.05, implied_return=0.06, revenue_growth=0.10,
                    roe=0.20, net_margin=0.15, price_pct_of_52w_range=0.6,
                    dcf_applicable=True)
        base.update(kw)
        return base

    return {
        "as_of": "2026-09-04", "rf": 0.045, "count": 9,
        "tickers": [
            row("CHEAP", upside_base=60.0, pe=15.0, fcf_multiple=10.0),   # явный лидер undervalued
            row("UND",  upside_base=30.0, pe=20.0),                       # недооценённая
            row("GROW", implied_growth=0.03, revenue_growth=0.20,
                        fcf_multiple=12.0, roe=0.16),                     # рост дёшево (gap 0.17)
            row("QUAL", roe=0.30, net_margin=0.25, upside_base=-5.0, pe=28.0),  # качество со скидкой
            row("RET",  implied_return=0.11, upside_base=5.0, roe=0.14, net_margin=0.11),  # доходность
            # TURN/JUNK: высокий P/E (45), чтобы не попадали в undervalued (pe<30);
            # turnaround pe не проверяет.
            row("TURN", price_pct_of_52w_range=0.1, upside_base=40.0, pe=45.0,
                        revenue_growth=-0.08, roe=0.22, net_margin=0.13),  # turnaround
            row("JUNK", price_pct_of_52w_range=0.1, upside_base=40.0, pe=45.0,
                        revenue_growth=-0.10, roe=0.05, net_margin=0.04),  # падающий нож — отсеять
            row("BANK", dcf_applicable=False),                            # DCF неприменим
            row("NEG",  fcf_positive=False),                             # отрицательный FCF
        ],
    }


def _syms(result):
    return [r["symbol"] for r in result.rows]


def test_all_presets_exist():
    assert set(PRESETS) == {"undervalued", "growth_cheap", "quality_discount",
                            "high_return", "turnaround"}


def test_bank_and_negfcf_never_appear():
    snap = _snapshot()
    for pid in PRESETS:
        syms = _syms(screen(snap, pid, ScreenFilters()))
        assert "BANK" not in syms
        assert "NEG" not in syms


def test_undervalued_keeps_positive_upside_cheap_pe_sorted():
    snap = _snapshot()
    res = screen(snap, "undervalued", ScreenFilters())
    syms = _syms(res)
    assert "QUAL" not in syms          # upside -5 → нужен upside>0
    assert "TURN" not in syms          # pe 45 → не проходит pe<30
    assert res.rows[0]["symbol"] == "CHEAP"        # макс. апсайд 60 сверху
    assert res.total_passed == len(res.rows)


def test_growth_cheap_ranks_by_gap():
    snap = _snapshot()
    res = screen(snap, "growth_cheap", ScreenFilters())
    # GROW: gap 0.20-0.03=0.17, лучший
    assert res.rows[0]["symbol"] == "GROW"


def test_quality_discount_requires_roe_and_margin():
    snap = _snapshot()
    syms = _syms(screen(snap, "quality_discount", ScreenFilters()))
    assert "QUAL" in syms       # roe0.30, margin0.25, upside-5>-10
    assert "RET" not in syms    # roe0.14<0.15


def test_high_return_beats_riskfree():
    snap = _snapshot()
    res = screen(snap, "high_return", ScreenFilters())
    assert res.rows[0]["symbol"] == "RET"          # 0.11 > rf 0.045, максимум


def test_turnaround_selects_beaten_down_with_fundamentals_and_flags_risk():
    snap = _snapshot()
    res = screen(snap, "turnaround", ScreenFilters())
    syms = _syms(res)
    assert "TURN" in syms       # дёшево + фундамент выше медианы
    assert "JUNK" not in syms   # дёшево, но roe/margin ниже медианы
    assert all(r.get("badge") == "risk" for r in res.rows)


def test_user_filters_tighten_on_top_of_preset():
    snap = _snapshot()
    res = screen(snap, "undervalued", ScreenFilters(min_upside=35.0))
    # min_upside=35 отсекает UND (30); остаётся CHEAP (60) — единственный с upside>=35 и pe<30
    assert _syms(res) == ["CHEAP"]
    assert all(r["upside_base"] >= 35.0 for r in res.rows)
    assert "UND" not in _syms(res)


def test_empty_result_is_safe():
    snap = _snapshot()
    res = screen(snap, "undervalued", ScreenFilters(min_upside=999.0))
    assert res.rows == []
    assert res.total_passed == 0


def test_limit_caps_rows():
    snap = _snapshot()
    res = screen(snap, "undervalued", ScreenFilters(), limit=1)
    assert len(res.rows) == 1
    assert res.total_passed >= 1     # total не обрезается лимитом


def test_market_cap_filters():
    snap = _snapshot()                     # все market_cap = 1e11
    # мин выше всех → пусто
    assert screen(snap, "undervalued", ScreenFilters(min_market_cap=2e11)).rows == []
    # макс ниже всех → пусто
    assert screen(snap, "undervalued", ScreenFilters(max_market_cap=5e10)).rows == []
    # диапазон, в который все попадают → CHEAP на месте
    res = screen(snap, "undervalued", ScreenFilters(min_market_cap=5e10, max_market_cap=2e11))
    assert res.rows[0]["symbol"] == "CHEAP"
