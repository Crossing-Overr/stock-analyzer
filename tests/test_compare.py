from core.data import TickerData
from core.compare import build_comparison_table, MetricRow


def _td(symbol, price, pe, roe):
    info = {"currentPrice": price, "trailingPE": pe, "returnOnEquity": roe,
            "longName": symbol}
    return TickerData.from_info(symbol, info, None, None)


def test_table_has_row_per_metric_and_column_per_ticker():
    tds = [_td("AAPL", 200, 30.0, 0.8), _td("MSFT", 400, 35.0, 0.4)]
    table = build_comparison_table(tds, base_upsides={"AAPL": 12.0, "MSFT": -5.0})
    assert [c for c in table.columns] == ["AAPL", "MSFT"]
    labels = [r.label for r in table.rows]
    assert "P/E" in labels
    assert "Апсайд (Base DCF)" in labels


def test_upside_row_uses_provided_values():
    tds = [_td("AAPL", 200, 30.0, 0.8), _td("MSFT", 400, 35.0, 0.4)]
    table = build_comparison_table(tds, base_upsides={"AAPL": 12.0, "MSFT": -5.0})
    upside_row = next(r for r in table.rows if r.label == "Апсайд (Base DCF)")
    assert upside_row.raw_values == [12.0, -5.0]


def test_best_worst_marked_lower_is_better_for_pe():
    tds = [_td("AAPL", 200, 30.0, 0.8), _td("MSFT", 400, 35.0, 0.4)]
    table = build_comparison_table(tds, base_upsides={"AAPL": 0.0, "MSFT": 0.0})
    pe_row = next(r for r in table.rows if r.label == "P/E")
    # ниже P/E лучше → AAPL (индекс 0) best, MSFT (индекс 1) worst
    assert pe_row.best_index == 0
    assert pe_row.worst_index == 1


def test_best_worst_marked_higher_is_better_for_roe():
    tds = [_td("AAPL", 200, 30.0, 0.8), _td("MSFT", 400, 35.0, 0.4)]
    table = build_comparison_table(tds, base_upsides={"AAPL": 0.0, "MSFT": 0.0})
    roe_row = next(r for r in table.rows if r.label == "ROE")
    assert roe_row.best_index == 0   # выше ROE лучше → AAPL
    assert roe_row.worst_index == 1


def test_missing_values_are_not_marked_best_worst():
    a = _td("AAPL", 200, 30.0, 0.8)
    b = _td("MSFT", 400, None, 0.4)   # нет P/E
    table = build_comparison_table([a, b], base_upsides={"AAPL": 0.0, "MSFT": 0.0})
    pe_row = next(r for r in table.rows if r.label == "P/E")
    assert pe_row.best_index == 0     # единственное валидное значение
    assert pe_row.worst_index == 0
