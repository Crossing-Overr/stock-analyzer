import math
import pandas as pd
import pytest
from core.data import safe, fmt_large, fmt_pct, fmt_mult, TickerData, subtract_series, tnx_to_rate

def test_safe_returns_default_for_none_nan_empty():
    assert safe({"x": None}, "x", "D") == "D"
    assert safe({"x": float("nan")}, "x", "D") == "D"
    assert safe({"x": "N/A"}, "x", "D") == "D"
    assert safe({"x": ""}, "x", "D") == "D"
    assert safe({}, "x", "D") == "D"

def test_safe_returns_value_when_present():
    assert safe({"x": 5}, "x") == 5
    assert safe({"x": "AAPL"}, "x") == "AAPL"

def test_fmt_large():
    assert fmt_large(2.5e12) == "$2.50T"
    assert fmt_large(3.1e9) == "$3.10B"
    assert fmt_large(4.2e6) == "$4.20M"
    assert fmt_large(500) == "$500"
    assert fmt_large(None) == "N/A"
    assert fmt_large(float("nan")) == "N/A"

def test_fmt_pct():
    assert fmt_pct(0.123) == "12.3%"
    assert fmt_pct(None) == "N/A"

def test_fmt_mult():
    assert fmt_mult(15.4) == "15.4x"
    assert fmt_mult(1.2, "") == "1.2"
    assert fmt_mult(None) == "N/A"

def test_tickerdata_from_info_extracts_and_computes_net_debt():
    info = {
        "longName": "Apple Inc.", "sector": "Technology", "currency": "USD",
        "currentPrice": 200.0, "previousClose": 195.0,
        "marketCap": 3.0e12, "totalDebt": 100.0, "totalCash": 40.0,
        "freeCashflow": 1.0e11, "sharesOutstanding": 1.5e10,
        "trailingPE": 30.0,
    }
    td = TickerData.from_info("AAPL", info, history=None, financials=None)
    assert td.name == "Apple Inc."
    assert td.price == 200.0
    assert td.net_debt == 60.0          # 100 - 40
    assert td.day_change_pct == pytest.approx((200 - 195) / 195 * 100)

def test_tickerdata_from_info_defaults_missing_fields():
    td = TickerData.from_info("XYZ", {"currentPrice": 10.0}, None, None)
    assert td.name == "XYZ"             # longName отсутствует → symbol
    assert td.market_cap is None
    assert td.net_debt == 0.0           # нет долга/кэша → 0


def test_dividend_yield_uses_trailing_fraction():
    # trailingAnnualDividendYield — дробь; храним как есть (fmt_pct ×100 = верно)
    td = TickerData.from_info("KO", {"currentPrice": 83.0,
                                     "trailingAnnualDividendYield": 0.02445,
                                     "dividendYield": 2.52}, None, None)
    assert td.dividend_yield == pytest.approx(0.02445)

def test_dividend_yield_falls_back_to_percent_field_scaled():
    # нет trailing → dividendYield приходит в процентах (2.52) → делим на 100
    td = TickerData.from_info("KO", {"currentPrice": 83.0, "dividendYield": 2.52},
                              None, None)
    assert td.dividend_yield == pytest.approx(0.0252)

def test_dividend_yield_none_when_absent():
    td = TickerData.from_info("XYZ", {"currentPrice": 10.0}, None, None)
    assert td.dividend_yield is None


def _cashflow(rows: dict):
    """Отчёт о ДДС как у yfinance: строки — статьи, столбцы — годы (newest-first)."""
    cols = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")]
    return pd.DataFrame.from_dict(rows, orient="index", columns=cols)


def test_subtract_series_elementwise():
    assert subtract_series([10.0, 20.0], [1.0, 2.0]) == [9.0, 18.0]


def test_subtract_series_bad_pair_becomes_nan():
    out = subtract_series([10.0, None], [1.0, 2.0])
    assert out[0] == 9.0
    assert math.isnan(out[1])


def test_subtract_series_empty():
    assert subtract_series([], [1.0]) == []
    assert subtract_series(None, None) == []


def test_fcf_ex_sbc_is_median_of_per_year_differences():
    cf = _cashflow({"Free Cash Flow": [30.0, 20.0, 10.0],
                    "Stock Based Compensation": [3.0, 2.0, 1.0]})
    td = TickerData.from_info("X", {"currentPrice": 5.0}, None, None, cf)
    assert td.fcf_normalized == 20.0                 # median(30,20,10)
    assert td.sbc_normalized == 2.0                  # median(3,2,1)
    assert td.fcf_normalized_ex_sbc == 18.0          # median(27,18,9), НЕ 20-2


def test_fcf_ex_sbc_none_when_sbc_row_absent():
    cf = _cashflow({"Free Cash Flow": [30.0, 20.0, 10.0]})
    td = TickerData.from_info("X", {"currentPrice": 5.0}, None, None, cf)
    assert td.fcf_normalized == 20.0
    assert td.sbc_normalized is None
    assert td.fcf_normalized_ex_sbc is None


def test_fcf_ex_sbc_none_without_cashflow():
    td = TickerData.from_info("X", {"currentPrice": 5.0, "freeCashflow": 7.0}, None, None)
    assert td.fcf_normalized == 7.0                  # откат на trailing
    assert td.fcf_normalized_ex_sbc is None


def test_tnx_to_rate_converts_percent_to_fraction():
    # ^TNX котируется в процентах: 4.541 → 0.04541
    assert tnx_to_rate(4.541) == pytest.approx(0.04541)


def test_tnx_to_rate_rejects_garbage():
    assert tnx_to_rate(None) is None
    assert tnx_to_rate(0.5) is None     # 0.005 — ниже санитарного минимума 1%
    assert tnx_to_rate(45.0) is None    # 0.45 — выше санитарного максимума 10%


def test_dcf_fcf_base_selection():
    cf = _cashflow({"Free Cash Flow": [30.0, 20.0, 10.0],
                    "Stock Based Compensation": [3.0, 2.0, 1.0]})
    td = TickerData.from_info("X", {"currentPrice": 5.0}, None, None, cf)
    assert td.dcf_fcf_base(subtract_sbc=True) == 18.0    # ex-SBC доступен
    assert td.dcf_fcf_base(subtract_sbc=False) == 20.0   # галочка выключена

    cf2 = _cashflow({"Free Cash Flow": [30.0, 20.0, 10.0]})
    td2 = TickerData.from_info("X", {"currentPrice": 5.0}, None, None, cf2)
    assert td2.dcf_fcf_base(subtract_sbc=True) == 20.0   # SBC нет → обычная база
