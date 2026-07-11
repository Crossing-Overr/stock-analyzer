import pytest
from core.data import safe, fmt_large, fmt_pct, fmt_mult, TickerData

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
