from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import streamlit as st
import yfinance as yf


# ─── safe + форматтеры ──────────────────────────────────────────────────────
def safe(info: dict, key: str, default: Any = None) -> Any:
    v = info.get(key, default)
    if v == "N/A" or v == "" or v is None:
        return default
    try:
        if isinstance(v, float) and np.isnan(v):
            return default
    except (TypeError, ValueError):
        pass
    return v


def _is_missing(n) -> bool:
    return n is None or (isinstance(n, float) and np.isnan(n))


def fmt_large(n) -> str:
    if _is_missing(n):
        return "N/A"
    if abs(n) >= 1e12:
        return f"${n / 1e12:.2f}T"
    if abs(n) >= 1e9:
        return f"${n / 1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:.2f}M"
    return f"${n:,.0f}"


def fmt_pct(n) -> str:
    if _is_missing(n):
        return "N/A"
    return f"{n * 100:.1f}%"


def fmt_mult(n, suffix: str = "x") -> str:
    if _is_missing(n):
        return "N/A"
    return f"{n:.1f}{suffix}"


# ─── TickerData ─────────────────────────────────────────────────────────────
@dataclass
class TickerData:
    symbol: str
    name: str
    sector: str
    industry: str
    country: str
    website: str
    currency: str

    price: Optional[float]
    previous_close: Optional[float]
    market_cap: Optional[float]
    enterprise_value: Optional[float]
    week52_high: Optional[float]
    week52_low: Optional[float]

    trailing_pe: Optional[float]
    forward_pe: Optional[float]
    price_to_sales: Optional[float]
    price_to_book: Optional[float]
    ev_to_ebitda: Optional[float]
    ev_to_revenue: Optional[float]
    peg: Optional[float]
    dividend_yield: Optional[float]

    total_revenue: Optional[float]
    gross_profits: Optional[float]
    ebitda: Optional[float]
    net_income: Optional[float]
    free_cashflow: Optional[float]
    total_debt: Optional[float]
    total_cash: Optional[float]

    gross_margins: Optional[float]
    ebitda_margins: Optional[float]
    profit_margins: Optional[float]
    roe: Optional[float]
    roa: Optional[float]
    revenue_growth: Optional[float]

    description: str
    employees: Optional[int]
    shares_outstanding: Optional[float]
    beta: Optional[float]
    short_percent_float: Optional[float]

    history: Any = None       # pandas DataFrame или None
    financials: Any = None    # pandas DataFrame или None

    @property
    def net_debt(self) -> float:
        debt = self.total_debt or 0.0
        cash = self.total_cash or 0.0
        return debt - cash

    @property
    def day_change_pct(self) -> float:
        if self.price and self.previous_close:
            return (self.price - self.previous_close) / self.previous_close * 100
        return 0.0

    @classmethod
    def from_info(cls, symbol, info, history, financials) -> "TickerData":
        return cls(
            symbol=symbol,
            name=safe(info, "longName", symbol),
            sector=safe(info, "sector", "—"),
            industry=safe(info, "industry", "—"),
            country=safe(info, "country", "—"),
            website=safe(info, "website", ""),
            currency=safe(info, "currency", "USD"),
            price=safe(info, "currentPrice") or safe(info, "regularMarketPrice"),
            previous_close=safe(info, "previousClose"),
            market_cap=safe(info, "marketCap"),
            enterprise_value=safe(info, "enterpriseValue"),
            week52_high=safe(info, "fiftyTwoWeekHigh"),
            week52_low=safe(info, "fiftyTwoWeekLow"),
            trailing_pe=safe(info, "trailingPE"),
            forward_pe=safe(info, "forwardPE"),
            price_to_sales=safe(info, "priceToSalesTrailing12Months"),
            price_to_book=safe(info, "priceToBook"),
            ev_to_ebitda=safe(info, "enterpriseToEbitda"),
            ev_to_revenue=safe(info, "enterpriseToRevenue"),
            peg=safe(info, "pegRatio"),
            dividend_yield=safe(info, "dividendYield"),
            total_revenue=safe(info, "totalRevenue"),
            gross_profits=safe(info, "grossProfits"),
            ebitda=safe(info, "ebitda"),
            net_income=safe(info, "netIncomeToCommon"),
            free_cashflow=safe(info, "freeCashflow"),
            total_debt=safe(info, "totalDebt"),
            total_cash=safe(info, "totalCash"),
            gross_margins=safe(info, "grossMargins"),
            ebitda_margins=safe(info, "ebitdaMargins"),
            profit_margins=safe(info, "profitMargins"),
            roe=safe(info, "returnOnEquity"),
            roa=safe(info, "returnOnAssets"),
            revenue_growth=safe(info, "revenueGrowth"),
            description=safe(info, "longBusinessSummary", "Описание недоступно."),
            employees=safe(info, "fullTimeEmployees"),
            shares_outstanding=safe(info, "sharesOutstanding"),
            beta=safe(info, "beta"),
            short_percent_float=safe(info, "shortPercentOfFloat"),
            history=history,
            financials=financials,
        )

    def has_price(self) -> bool:
        return self.price is not None


# ─── Загрузка с кэшем ───────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def load_ticker(symbol: str) -> Optional[TickerData]:
    """Тянет данные из Yahoo и возвращает TickerData, либо None если тикер битый."""
    try:
        tk = yf.Ticker(symbol)
        info = tk.info
        if not info:
            return None
        history = tk.history(period="1y")
        try:
            financials = tk.financials
        except Exception:
            financials = None
        td = TickerData.from_info(symbol, info, history, financials)
        return td if td.has_price() else None
    except Exception:
        return None
