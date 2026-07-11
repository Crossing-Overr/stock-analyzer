import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Analysator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 12px;
        padding: 16px 20px;
        margin: 4px 0;
    }
    .metric-label { color: #a6adc8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { color: #cdd6f4; font-size: 22px; font-weight: 700; margin-top: 4px; }
    .metric-sub   { color: #6c7086; font-size: 12px; margin-top: 2px; }
    .scenario-bull { border-left: 4px solid #a6e3a1; }
    .scenario-base { border-left: 4px solid #89b4fa; }
    .scenario-bear { border-left: 4px solid #f38ba8; }
    .upside-pos { color: #a6e3a1; font-weight: 700; }
    .upside-neg { color: #f38ba8; font-weight: 700; }
    .section-header {
        color: #cdd6f4;
        font-size: 18px;
        font-weight: 600;
        margin: 24px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid #313244;
    }
    div[data-testid="stMetric"] {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 12px;
        padding: 12px 16px;
    }
</style>
""", unsafe_allow_html=True)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def fmt_large(n):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "N/A"
    if abs(n) >= 1e12:
        return f"${n/1e12:.2f}T"
    if abs(n) >= 1e9:
        return f"${n/1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"

def fmt_pct(n):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "N/A"
    return f"{n*100:.1f}%"

def fmt_mult(n, suffix="x"):
    if n is None or (isinstance(n, float) and np.isnan(n)):
        return "N/A"
    return f"{n:.1f}{suffix}"

def safe(info, key, default=None):
    v = info.get(key, default)
    if v == "N/A" or v == "" or v is None:
        return default
    try:
        if isinstance(v, float) and np.isnan(v):
            return default
    except:
        pass
    return v


# ─── DCF ─────────────────────────────────────────────────────────────────────
def run_dcf(fcf_base, growth_rates, wacc, terminal_growth, years, shares, net_debt):
    """
    2-phase DCF with growth fade.

    Instead of applying a constant growth rate for every year (which
    compounds unrealistically), the growth rate declines linearly from the
    starting rate (year 1) toward the terminal growth rate (final year).
    This "fade" is standard practice — no company grows at 20%/yr forever,
    and it keeps the terminal value from dominating the whole valuation.

    growth_rates: list of *starting* annual growth rates (bear/base/bull).
    Returns intrinsic value per share plus terminal-value share.
    """
    results = {}
    labels = ["🐻 Bear", "📊 Base", "🐂 Bull"]
    colors = ["#f38ba8", "#89b4fa", "#a6e3a1"]

    for label, color, g_start in zip(labels, colors, growth_rates):
        fcfs = []
        growth_path = []
        fcf = fcf_base
        for y in range(1, years + 1):
            # Linear fade: year 1 uses g_start, final year uses terminal_growth
            if years > 1:
                g = g_start + (terminal_growth - g_start) * (y - 1) / (years - 1)
            else:
                g = g_start
            growth_path.append(g)
            fcf = fcf * (1 + g)
            pv = fcf / (1 + wacc) ** y
            fcfs.append(pv)

        terminal_fcf = fcf * (1 + terminal_growth)
        terminal_value = terminal_fcf / (wacc - terminal_growth)
        pv_terminal = terminal_value / (1 + wacc) ** years

        enterprise_value = sum(fcfs) + pv_terminal
        equity_value = enterprise_value - net_debt
        intrinsic = equity_value / shares if shares > 0 else 0
        tv_share = pv_terminal / enterprise_value if enterprise_value > 0 else 0

        results[label] = {
            "color": color,
            "growth": g_start,
            "growth_path": growth_path,
            "fcfs_pv": fcfs,
            "pv_terminal": pv_terminal,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "intrinsic": intrinsic,
            "tv_share": tv_share,
        }
    return results


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 Stock Analysator")
    st.markdown("---")
    ticker_input = st.text_input("Тикер", value="AAPL", placeholder="AAPL, MSFT, NVDA...").upper().strip()

    st.markdown("### ⚙️ DCF параметры")
    years = st.slider("Горизонт прогноза (лет)", 3, 10, 5)
    wacc = st.slider("WACC (%)", 5.0, 20.0, 10.0, 0.5) / 100
    terminal_growth = st.slider("Терминальный рост (%)", 1.0, 5.0, 2.5, 0.25) / 100

    st.markdown("#### Стартовый рост FCF (%/год)")
    st.caption("Рост в 1-й год. Дальше линейно затухает к терминальному.")
    bull_g = st.slider("🐂 Bull", 5, 40, 15) / 100
    base_g = st.slider("📊 Base", 0, 30, 8) / 100
    bear_g = st.slider("-🐻 Bear", -10, 15, 2) / 100

    st.markdown("---")
    st.caption("Данные: Yahoo Finance (yfinance)")


# ─── Main ─────────────────────────────────────────────────────────────────────
if not ticker_input:
    st.info("Введи тикер в боковой панели")
    st.stop()

with st.spinner(f"Загружаю данные по {ticker_input}..."):
    try:
        tk = yf.Ticker(ticker_input)
        info = tk.info
        hist = tk.history(period="1y")
        fin  = tk.financials       # annual income statement
        bal  = tk.balance_sheet
        cf   = tk.cashflow
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        st.stop()

if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
    st.error(f"Тикер «{ticker_input}» не найден или данных нет.")
    st.stop()

# ─── Company header ───────────────────────────────────────────────────────────
name    = safe(info, "longName", ticker_input)
sector  = safe(info, "sector", "—")
industry= safe(info, "industry", "—")
country = safe(info, "country", "—")
website = safe(info, "website", "")
price   = safe(info, "currentPrice") or safe(info, "regularMarketPrice", 0)
currency= safe(info, "currency", "USD")

col_logo, col_info = st.columns([1, 6])
with col_info:
    st.markdown(f"# {name} &nbsp; `{ticker_input}`")
    st.markdown(f"**{sector}** · {industry} · {country}" + (f" · [{website}]({website})" if website else ""))

st.markdown("---")

# ─── Price + quick metrics ─────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

prev_close = safe(info, "previousClose", price)
day_chg = ((price - prev_close) / prev_close * 100) if prev_close else 0
arrow = "▲" if day_chg >= 0 else "▼"
chg_color = "normal" if day_chg >= 0 else "inverse"

c1.metric("Цена", f"{price:.2f} {currency}", f"{arrow} {abs(day_chg):.2f}%")
c2.metric("Рын. капитализация", fmt_large(safe(info, "marketCap")))
c3.metric("EV", fmt_large(safe(info, "enterpriseValue")))
c4.metric("52w High", f"{safe(info, 'fiftyTwoWeekHigh', 0):.2f}")
c5.metric("52w Low",  f"{safe(info, 'fiftyTwoWeekLow', 0):.2f}")

# ─── Price chart ─────────────────────────────────────────────────────────────
if not hist.empty:
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(
        x=hist.index, y=hist["Close"],
        mode="lines",
        line=dict(color="#89b4fa", width=2),
        fill="tozeroy",
        fillcolor="rgba(137,180,250,0.08)",
        name="Цена",
    ))
    fig_price.update_layout(
        height=280, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=False, color="#6c7086"),
        yaxis=dict(showgrid=True, gridcolor="#313244", color="#6c7086"),
        plot_bgcolor="#181825", paper_bgcolor="#181825",
        showlegend=False,
    )
    st.plotly_chart(fig_price, use_container_width=True)

# ─── Мультипликаторы ──────────────────────────────────────────────────────────
st.markdown('<div class="section-header">📊 Мультипликаторы</div>', unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6, m7, m8 = st.columns(8)

m1.metric("P/E",          fmt_mult(safe(info, "trailingPE")))
m2.metric("Forward P/E",  fmt_mult(safe(info, "forwardPE")))
m3.metric("P/S",          fmt_mult(safe(info, "priceToSalesTrailing12Months")))
m4.metric("P/B",          fmt_mult(safe(info, "priceToBook")))
m5.metric("EV/EBITDA",    fmt_mult(safe(info, "enterpriseToEbitda")))
m6.metric("EV/Revenue",   fmt_mult(safe(info, "enterpriseToRevenue")))
m7.metric("PEG",          fmt_mult(safe(info, "pegRatio")))
m8.metric("Div. Yield",   fmt_pct(safe(info, "dividendYield")))

# ─── Финансовые показатели ────────────────────────────────────────────────────
st.markdown('<div class="section-header">💰 Финансовые показатели (TTM)</div>', unsafe_allow_html=True)
f1, f2, f3, f4, f5, f6 = st.columns(6)

f1.metric("Выручка",          fmt_large(safe(info, "totalRevenue")))
f2.metric("Валовая прибыль",  fmt_large(safe(info, "grossProfits")))
f3.metric("EBITDA",           fmt_large(safe(info, "ebitda")))
f4.metric("Чистая прибыль",   fmt_large(safe(info, "netIncomeToCommon")))
f5.metric("FCF",              fmt_large(safe(info, "freeCashflow")))
f6.metric("Долг",             fmt_large(safe(info, "totalDebt")))

f7, f8, f9, f10, f11, f12 = st.columns(6)
f7.metric("Gross Margin",     fmt_pct(safe(info, "grossMargins")))
f8.metric("EBITDA Margin",    fmt_pct(safe(info, "ebitdaMargins")))
f9.metric("Net Margin",       fmt_pct(safe(info, "profitMargins")))
f10.metric("ROE",             fmt_pct(safe(info, "returnOnEquity")))
f11.metric("ROA",             fmt_pct(safe(info, "returnOnAssets")))
f12.metric("Рост выручки",    fmt_pct(safe(info, "revenueGrowth")))

# ─── О компании ──────────────────────────────────────────────────────────────
with st.expander("ℹ️ О компании"):
    desc = safe(info, "longBusinessSummary", "Описание недоступно.")
    st.write(desc)

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Сотрудников",  f"{safe(info, 'fullTimeEmployees', 0):,}" if safe(info, 'fullTimeEmployees') else "N/A")
    d2.metric("Акций в обращ.", fmt_large(safe(info, "sharesOutstanding")))
    d3.metric("Beta",          fmt_mult(safe(info, "beta"), ""))
    d4.metric("Short Float %", fmt_pct(safe(info, "shortPercentOfFloat")))

# ─── DCF ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🔮 DCF — три сценария</div>', unsafe_allow_html=True)

fcf_raw    = safe(info, "freeCashflow")
shares_raw = safe(info, "sharesOutstanding")
total_debt = safe(info, "totalDebt", 0) or 0
cash       = safe(info, "totalCash", 0) or 0
net_debt   = total_debt - cash

if not fcf_raw or not shares_raw:
    st.warning("Недостаточно данных для DCF (нет FCF или кол-ва акций). Попробуй другой тикер.")
else:
    dcf = run_dcf(
        fcf_base      = fcf_raw,
        growth_rates  = [bear_g, base_g, bull_g],
        wacc          = wacc,
        terminal_growth = terminal_growth,
        years         = years,
        shares        = shares_raw,
        net_debt      = net_debt,
    )

    bear_res, base_res, bull_res = dcf["🐻 Bear"], dcf["📊 Base"], dcf["🐂 Bull"]

    # Карточки сценариев
    sc1, sc2, sc3 = st.columns(3)

    for col, (label, res), css_class in zip(
        [sc1, sc2, sc3],
        dcf.items(),
        ["scenario-bear", "scenario-base", "scenario-bull"],
    ):
        iv = res["intrinsic"]
        upside = ((iv - price) / price * 100) if price else 0
        sign = "+" if upside >= 0 else ""
        upside_cls = "upside-pos" if upside >= 0 else "upside-neg"

        g_end = res["growth_path"][-1] if res.get("growth_path") else terminal_growth
        with col:
            st.markdown(f"""
            <div class="metric-card {css_class}">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{f"${iv:.2f}" if iv > 0 else "N/A"}</div>
                <div class="metric-sub">
                    Рост FCF: <b>{res['growth']*100:.0f}% → {g_end*100:.1f}%</b><br>
                    Апсайд: <span class="{upside_cls}">{sign}{upside:.1f}%</span><br>
                    Доля терм. стоим.: <b>{res['tv_share']*100:.0f}%</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.caption(f"WACC: {wacc*100:.1f}% · Терминальный рост: {terminal_growth*100:.1f}% · Горизонт: {years} лет · Чистый долг: {fmt_large(net_debt)}")

    # Предупреждение, если терминальная стоимость доминирует (типичная ловушка DCF)
    max_tv = max(res["tv_share"] for res in dcf.values())
    if max_tv > 0.75:
        st.warning(
            f"⚠️ Терминальная стоимость даёт до {max_tv*100:.0f}% оценки — "
            "результат сильно зависит от WACC и терминального роста, а не от прогноза FCF. "
            "Увеличь горизонт или снизь стартовый рост для более консервативной оценки."
        )

    # Waterfall chart для Base сценария
    st.markdown("##### Структура стоимости (Base сценарий)")
    years_labels = [f"Год {i+1}" for i in range(years)]
    years_labels.append("Терминальная стоимость")

    bar_vals = list(base_res["fcfs_pv"]) + [base_res["pv_terminal"]]

    fig_dcf = go.Figure()
    fig_dcf.add_trace(go.Bar(
        x=years_labels,
        y=bar_vals,
        marker_color=["#89b4fa"] * years + ["#cba6f7"],
        text=[fmt_large(v) for v in bar_vals],
        textposition="outside",
        textfont=dict(color="#cdd6f4", size=10),
    ))
    fig_dcf.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=False, color="#6c7086"),
        yaxis=dict(showgrid=True, gridcolor="#313244", color="#6c7086", tickformat="$.2s"),
        plot_bgcolor="#181825", paper_bgcolor="#181825",
        showlegend=False,
    )
    st.plotly_chart(fig_dcf, use_container_width=True)

    # Tornado — апсайд по трём сценариям
    st.markdown("##### Справедливая цена vs текущая")
    scenarios_labels = ["🐻 Bear", "📊 Base", "🐂 Bull"]
    intrinsics = [dcf[s]["intrinsic"] for s in scenarios_labels]
    upsides    = [(iv - price) / price * 100 if price else 0 for iv in intrinsics]
    bar_colors = ["#f38ba8", "#89b4fa", "#a6e3a1"]

    fig_up = go.Figure()
    fig_up.add_trace(go.Bar(
        x=scenarios_labels,
        y=intrinsics,
        name="Справедливая цена",
        marker_color=bar_colors,
        text=[f"${iv:.2f}" for iv in intrinsics],
        textposition="outside",
    ))
    fig_up.add_hline(
        y=price,
        line_dash="dot",
        line_color="#f9e2af",
        annotation_text=f"Текущая: ${price:.2f}",
        annotation_font_color="#f9e2af",
    )
    fig_up.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=False, color="#6c7086"),
        yaxis=dict(showgrid=True, gridcolor="#313244", color="#6c7086", tickprefix="$"),
        plot_bgcolor="#181825", paper_bgcolor="#181825",
        showlegend=False,
    )
    st.plotly_chart(fig_up, use_container_width=True)

# ─── Исторические финансы ────────────────────────────────────────────────────
st.markdown('<div class="section-header">📅 История финансов</div>', unsafe_allow_html=True)

try:
    if fin is not None and not fin.empty:
        revenue_row = None
        ni_row      = None
        for key in ["Total Revenue", "Revenue"]:
            if key in fin.index:
                revenue_row = fin.loc[key]
                break
        for key in ["Net Income", "Net Income Common Stockholders"]:
            if key in fin.index:
                ni_row = fin.loc[key]
                break

        if revenue_row is not None:
            cols_fin = sorted(revenue_row.index)
            rev_vals = [revenue_row[c] for c in cols_fin]
            ni_vals  = [ni_row[c] if ni_row is not None else 0 for c in cols_fin]
            years_fin = [str(c.year) for c in cols_fin]

            fig_fin = make_subplots(specs=[[{"secondary_y": True}]])
            fig_fin.add_trace(go.Bar(
                x=years_fin, y=rev_vals,
                name="Выручка", marker_color="#89b4fa", opacity=0.8,
            ), secondary_y=False)
            fig_fin.add_trace(go.Scatter(
                x=years_fin, y=ni_vals,
                name="Чистая прибыль", mode="lines+markers",
                line=dict(color="#a6e3a1", width=3),
                marker=dict(size=8),
            ), secondary_y=True)
            fig_fin.update_layout(
                height=320,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis=dict(showgrid=False, color="#6c7086"),
                yaxis=dict(showgrid=True, gridcolor="#313244", color="#89b4fa", tickformat="$.2s", title="Выручка"),
                yaxis2=dict(color="#a6e3a1", tickformat="$.2s", title="Чистая прибыль"),
                plot_bgcolor="#181825", paper_bgcolor="#181825",
                legend=dict(bgcolor="#1e1e2e", bordercolor="#313244"),
            )
            st.plotly_chart(fig_fin, use_container_width=True)
except Exception:
    st.caption("Историческая отчётность недоступна для этого тикера.")

# ─── Footer ──────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("⚠️ Stock Analysator — только для образовательных целей. Не является инвестиционной рекомендацией.")
