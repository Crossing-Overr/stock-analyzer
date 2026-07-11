import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.data import fmt_large

_PLOT_BG = "#181825"
_GRID = "#313244"
_AXIS = "#6c7086"

_SCENARIO_META = {
    "bear": ("🐻 Bear", "scenario-bear", "#f38ba8"),
    "base": ("📊 Base", "scenario-base", "#89b4fa"),
    "bull": ("🐂 Bull", "scenario-bull", "#a6e3a1"),
}


def section_header(text: str) -> None:
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def price_chart(history) -> None:
    if history is None or history.empty:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history.index, y=history["Close"], mode="lines",
        line=dict(color="#89b4fa", width=2),
        fill="tozeroy", fillcolor="rgba(137,180,250,0.08)", name="Цена",
    ))
    fig.update_layout(
        height=280, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=False, color=_AXIS),
        yaxis=dict(showgrid=True, gridcolor=_GRID, color=_AXIS),
        plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def scenario_card(col, name: str, res, price: float) -> None:
    label, css_class, _ = _SCENARIO_META[name]
    iv = res.intrinsic
    upside = ((iv - price) / price * 100) if price else 0
    sign = "+" if upside >= 0 else ""
    upside_cls = "upside-pos" if upside >= 0 else "upside-neg"
    g_end = res.growth_path[-1] if res.growth_path else 0.0
    with col:
        st.markdown(f"""
        <div class="metric-card {css_class}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{f"${iv:.2f}" if iv > 0 else "N/A"}</div>
            <div class="metric-sub">
                Рост FCF: <b>{res.growth_start*100:.0f}% → {g_end*100:.1f}%</b><br>
                Апсайд: <span class="{upside_cls}">{sign}{upside:.1f}%</span><br>
                Доля терм. стоим.: <b>{res.tv_share*100:.0f}%</b>
            </div>
        </div>
        """, unsafe_allow_html=True)


def dcf_waterfall(base_res, years: int) -> None:
    labels = [f"Год {i+1}" for i in range(years)] + ["Терминальная стоимость"]
    vals = list(base_res.fcfs_pv) + [base_res.pv_terminal]
    fig = go.Figure(go.Bar(
        x=labels, y=vals,
        marker_color=["#89b4fa"] * years + ["#cba6f7"],
        text=[fmt_large(v) for v in vals], textposition="outside",
        textfont=dict(color="#cdd6f4", size=10),
    ))
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=False, color=_AXIS),
        yaxis=dict(showgrid=True, gridcolor=_GRID, color=_AXIS, tickformat="$.2s"),
        plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def dcf_fair_value(dcf_results: dict, price: float) -> None:
    order = ["bear", "base", "bull"]
    labels = [_SCENARIO_META[n][0] for n in order]
    intrinsics = [dcf_results[n].intrinsic for n in order]
    colors = [_SCENARIO_META[n][2] for n in order]
    fig = go.Figure(go.Bar(
        x=labels, y=intrinsics, marker_color=colors,
        text=[f"${iv:.2f}" for iv in intrinsics], textposition="outside",
    ))
    fig.add_hline(y=price, line_dash="dot", line_color="#f9e2af",
                  annotation_text=f"Текущая: ${price:.2f}",
                  annotation_font_color="#f9e2af")
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=False, color=_AXIS),
        yaxis=dict(showgrid=True, gridcolor=_GRID, color=_AXIS, tickprefix="$"),
        plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def financials_history(financials) -> None:
    try:
        if financials is None or financials.empty:
            st.caption("Историческая отчётность недоступна для этого тикера.")
            return
        rev_row = ni_row = None
        for key in ["Total Revenue", "Revenue"]:
            if key in financials.index:
                rev_row = financials.loc[key]
                break
        for key in ["Net Income", "Net Income Common Stockholders"]:
            if key in financials.index:
                ni_row = financials.loc[key]
                break
        if rev_row is None:
            st.caption("Историческая отчётность недоступна для этого тикера.")
            return
        cols = sorted(rev_row.index)
        rev_vals = [rev_row[c] for c in cols]
        ni_vals = [ni_row[c] if ni_row is not None else 0 for c in cols]
        years_fin = [str(c.year) for c in cols]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=years_fin, y=rev_vals, name="Выручка",
                             marker_color="#89b4fa", opacity=0.8), secondary_y=False)
        fig.add_trace(go.Scatter(x=years_fin, y=ni_vals, name="Чистая прибыль",
                                 mode="lines+markers", line=dict(color="#a6e3a1", width=3),
                                 marker=dict(size=8)), secondary_y=True)
        fig.update_layout(
            height=320, margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(showgrid=False, color=_AXIS),
            yaxis=dict(showgrid=True, gridcolor=_GRID, color="#89b4fa", tickformat="$.2s", title="Выручка"),
            yaxis2=dict(color="#a6e3a1", tickformat="$.2s", title="Чистая прибыль"),
            plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG,
            legend=dict(bgcolor="#1e1e2e", bordercolor=_GRID),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.caption("Историческая отчётность недоступна для этого тикера.")
