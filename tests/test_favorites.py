from core.favorites import normalize, add_symbol, remove_symbol


def test_normalize_uppercases_strips_dedups_preserves_order():
    assert normalize([" aapl ", "MSFT", "aapl", "", "nvda"]) == ["AAPL", "MSFT", "NVDA"]


def test_normalize_handles_none():
    assert normalize(None) == []


def test_add_symbol_appends_new():
    assert add_symbol(["AAPL"], "msft") == ["AAPL", "MSFT"]


def test_add_symbol_is_idempotent():
    assert add_symbol(["AAPL"], "aapl") == ["AAPL"]


def test_remove_symbol():
    assert remove_symbol(["AAPL", "MSFT"], "aapl") == ["MSFT"]


def test_remove_missing_is_noop():
    assert remove_symbol(["AAPL"], "TSLA") == ["AAPL"]
