import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.data import fmt_large
from ui.theme import COLORS, SCENARIO_META, verdict_for

_PLOT_BG = COLORS["surface"]
_GRID = COLORS["border"]
_AXIS = COLORS["text_muted"]

# подпись + цвет сценария берём из общих токенов
_SCENARIO_EMOJI = {"bear": "🐻", "base": "📊", "bull": "🐂"}


def _scenario(name):
    """(подпись с эмодзи, цвет) для сценария bear/base/bull."""
    label, color_key = SCENARIO_META[name]
    return f"{_SCENARIO_EMOJI[name]} {label}", COLORS[color_key]


def section_header(text: str) -> None:
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def price_chart(history) -> None:
    if history is None or history.empty:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history.index, y=history["Close"], mode="lines",
        line=dict(color=COLORS["accent"], width=2),
        fill="tozeroy", fillcolor="rgba(99,102,241,0.10)", name="Цена",
    ))
    fig.update_layout(
        height=280, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=False, color=_AXIS),
        yaxis=dict(showgrid=True, gridcolor=_GRID, color=_AXIS),
        plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def scenario_card(col, name: str, res, price: float) -> None:
    label, accent = _scenario(name)
    iv = res.intrinsic
    upside = ((iv - price) / price * 100) if price else 0
    sign = "+" if upside >= 0 else ""
    upside_cls = "upside-pos" if upside >= 0 else "upside-neg"
    g_end = res.growth_path[-1] if res.growth_path else 0.0
    with col:
        st.markdown(f"""
        <div class="metric-card" style="border-left:3px solid {accent}">
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
        marker_color=[COLORS["accent"]] * years + [COLORS["accent2"]],
        text=[fmt_large(v) for v in vals], textposition="outside",
        textfont=dict(color=COLORS["text"], size=10),
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
    labels = [_scenario(n)[0] for n in order]
    intrinsics = [dcf_results[n].intrinsic for n in order]
    colors = [_scenario(n)[1] for n in order]
    fig = go.Figure(go.Bar(
        x=labels, y=intrinsics, marker_color=colors,
        text=[f"${iv:.2f}" for iv in intrinsics], textposition="outside",
    ))
    fig.add_hline(y=price, line_dash="dot", line_color=COLORS["warn"],
                  annotation_text=f"Текущая: ${price:.2f}",
                  annotation_font_color=COLORS["warn"])
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
                             marker_color=COLORS["accent"], opacity=0.8), secondary_y=False)
        fig.add_trace(go.Scatter(x=years_fin, y=ni_vals, name="Чистая прибыль",
                                 mode="lines+markers", line=dict(color=COLORS["pos"], width=3),
                                 marker=dict(size=8)), secondary_y=True)
        fig.update_layout(
            height=320, margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(showgrid=False, color=_AXIS),
            yaxis=dict(showgrid=True, gridcolor=_GRID, color=COLORS["accent"], tickformat="$.2s", title="Выручка"),
            yaxis2=dict(color=COLORS["pos"], tickformat="$.2s", title="Чистая прибыль"),
            plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG,
            legend=dict(bgcolor=COLORS["surface"], bordercolor=_GRID),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.caption("Историческая отчётность недоступна для этого тикера.")


def reverse_dcf_cards(implied_growth_value, implied_return_value,
                      terminal_growth: float, revenue_growth, risk_free=None) -> None:
    """Две карточки: заложенный в цену рост и ожидаемая доходность."""
    c1, c2 = st.columns(2)

    with c1:
        if implied_growth_value is None:
            value = "N/A"
            sub = "Не определяется в диапазоне −50%…+100%"
        else:
            value = f"{implied_growth_value * 100:.1f}%"
            sub = f"в 1-й год → {terminal_growth * 100:.1f}% к концу горизонта"
            if revenue_growth is not None:
                sub += (f"<br>Факт. рост выручки: "
                        f"<b>{revenue_growth * 100:.1f}%</b>")
        st.markdown(f"""
        <div class="metric-card" style="border-left:3px solid {COLORS['accent']}">
            <div class="metric-label">Заложенный рост FCF</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        if implied_return_value is None:
            value = "N/A"
            sub = "Не определяется в диапазоне"
        else:
            value = f"{implied_return_value * 100:.1f}%"
            ref = (f"{risk_free*100:.1f}%" if risk_free else "4%")
            sub = ("годовых при росте Base-сценария<br>"
                   f"Ориентир: гособлигации 10 лет ≈ {ref}")
        st.markdown(f"""
        <div class="metric-card" style="border-left:3px solid {COLORS['accent']}">
            <div class="metric-label">Ожидаемая доходность</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """, unsafe_allow_html=True)


def sensitivity_table(grid, mode: str = "upside") -> None:
    """
    Сетка чувствительности. mode: "upside" (апсайд %) или "price" (цена $).
    Рендерим сырым HTML — в нём $ не превращается в формулу LaTeX.
    """
    is_mult = grid.multiples is not None
    corner = "Мультипл. ↓ / WACC →" if is_mult else "Терм. рост ↓ / WACC →"
    header = "".join(
        f"<th style='padding:6px 10px;text-align:right'>{w * 100:.1f}%</th>"
        for w in grid.waccs
    )
    rows_html = ""
    for row in grid.cells:
        cells = ""
        for cell in row:
            if cell.intrinsic is None:
                cells += ("<td style='padding:6px 10px;text-align:right;"
                          f"color:{COLORS['text_muted']}'>—</td>")
                continue
            if mode == "price":
                text = f"${cell.intrinsic:.2f}"
            else:
                text = f"{cell.upside:+.0f}%" if cell.upside is not None else "N/A"
            cls = "cmp-best" if (cell.upside or 0) > 0 else "cmp-worst"
            border = f"border:2px solid {COLORS['warn']};" if cell.is_current else ""
            cells += (f"<td class='{cls}' style='padding:6px 10px;"
                      f"text-align:right;{border}'>{text}</td>")
        label = (f"{row[0].multiple:.0f}x" if is_mult
                 else f"{row[0].terminal_growth * 100:.2f}%")
        rows_html += (f"<tr><td style='padding:6px 10px;color:{COLORS['text_dim']}'>"
                      f"{label}</td>{cells}</tr>")

    st.markdown(f"""
    <table style='width:100%;border-collapse:collapse;background:{COLORS['surface']};
    border:1px solid {COLORS['border']};border-radius:12px'>
    <thead><tr><th style='padding:6px 10px;text-align:left'>{corner}</th>
    {header}</tr></thead>
    <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)


def ticker_header(td) -> None:
    """Хедер тикера: аватар-градиент, название, сектор, цена и дневное изменение."""
    chg = td.day_change_pct
    chg_color = COLORS["pos"] if chg >= 0 else COLORS["neg"]
    sign = "+" if chg >= 0 else ""
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:13px;margin-bottom:16px">
      <div style="width:44px;height:44px;border-radius:13px;flex:none;
      background:linear-gradient(135deg,{COLORS['accent']},{COLORS['accent2']});
      display:flex;align-items:center;justify-content:center;
      color:#fff;font-weight:700;font-size:18px">{td.symbol[:1]}</div>
      <div style="flex:1;min-width:0">
        <div style="color:{COLORS['text']};font-size:19px;font-weight:600;
        letter-spacing:-0.01em;overflow:hidden;text-overflow:ellipsis;
        white-space:nowrap">{td.name}</div>
        <div style="color:{COLORS['text_muted']};font-size:12px">{td.symbol} · {td.sector}</div>
      </div>
      <div style="text-align:right;flex:none">
        <div style="color:{COLORS['text']};font-size:22px;font-weight:700">${td.price:.2f}</div>
        <div style="color:{chg_color};font-size:12.5px;font-weight:600">{sign}{chg:.2f}%</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def scenario_scale(bear: float, base: float, bull: float, price: float) -> str:
    """
    HTML-шкала bear/base/bull относительно рыночной цены.
    Возвращает разметку (вставляется внутрь карточки-вердикта).
    """
    hi = max(bull, price) * 1.05
    pct = lambda v: max(0.0, min(100.0, v / hi * 100)) if hi > 0 else 0.0
    return f"""
    <div style="position:relative;height:6px;background:{COLORS['elevated']};
    border-radius:3px;margin:12px 0 6px">
      <div style="position:absolute;left:0;width:{pct(base):.1f}%;height:100%;
      background:linear-gradient(90deg,{COLORS['neg']},{COLORS['warn']});border-radius:3px"></div>
      <div style="position:absolute;left:{pct(bull):.1f}%;width:2px;height:12px;top:-3px;
      background:{COLORS['pos']};border-radius:1px"></div>
      <div style="position:absolute;left:{pct(price):.1f}%;width:2px;height:12px;top:-3px;
      background:{COLORS['text']};border-radius:1px"></div>
    </div>
    <div style="display:flex;justify-content:space-between;color:{COLORS['text_muted']};font-size:10px">
      <span>bear ${bear:.0f}</span>
      <span style="color:{COLORS['text_dim']}">base ${base:.0f}</span>
      <span style="color:{COLORS['pos']}">bull ${bull:.0f}</span>
      <span style="color:{COLORS['text']};font-weight:600">рынок ${price:.0f}</span>
    </div>
    """


def verdict_card(dcf_results, price: float, wacc: float) -> None:
    """
    Карточка-вердикт: НЕДООЦЕНЕНА / СПРАВЕДЛИВО / ПЕРЕОЦЕНЕНА, справедливая цена,
    апсайд и шкала сценариев. Главный блок страницы «Анализ».
    """
    base_iv = dcf_results["base"].intrinsic
    upside = ((base_iv - price) / price * 100) if (price and base_iv > 0) else None
    v = verdict_for(upside)

    if v is None:
        st.markdown(f"""
        <div style="background:{COLORS['surface']};border:1px solid {COLORS['border']};
        border-radius:16px;padding:18px;margin-bottom:12px">
          <div style="color:{COLORS['text_dim']};font-size:13px">
            Справедливая цена не определяется: расчётная стоимость собственного
            капитала ≤ 0 (долг и SBC съедают денежный поток).
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    label, ckey = v
    tint = COLORS[ckey]
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{tint}22,{tint}08);
    border:1px solid {tint}44;border-radius:16px;padding:18px;margin-bottom:12px">
      <div style="display:flex;align-items:center;gap:9px;margin-bottom:10px">
        <span style="background:{tint}33;color:{tint};font-size:10px;font-weight:700;
        padding:4px 11px;border-radius:99px;letter-spacing:0.04em">{label}</span>
        <span style="color:{COLORS['text_muted']};font-size:11px">
        DCF · Base · WACC {wacc*100:.1f}%</span>
      </div>
      <div style="display:flex;align-items:flex-end;gap:14px">
        <div>
          <div style="color:{COLORS['text_dim']};font-size:11px;margin-bottom:2px">Справедливая цена</div>
          <div style="color:{COLORS['text']};font-size:32px;font-weight:700;
          letter-spacing:-0.02em">${base_iv:.2f}</div>
        </div>
        <div style="padding-bottom:6px">
          <div style="color:{tint};font-size:18px;font-weight:700">{upside:+.1f}%</div>
        </div>
      </div>
      {scenario_scale(dcf_results['bear'].intrinsic, base_iv,
                      dcf_results['bull'].intrinsic, price)}
    </div>
    """, unsafe_allow_html=True)


def metric_rows(pairs) -> None:
    """Компактные строки «подпись — значение» вместо стены одинаковых плиток.
    pairs: список кортежей (подпись, значение-строка)."""
    rows = "".join(
        f"""<div style="display:flex;justify-content:space-between;padding:9px 14px;
        border-bottom:1px solid {COLORS['elevated']}">
          <span style="color:{COLORS['text_dim']};font-size:12.5px">{k}</span>
          <span style="color:{COLORS['text']};font-size:12.5px;font-weight:600">{v}</span>
        </div>""" for k, v in pairs)
    st.markdown(f"""
    <div style="background:{COLORS['surface']};border:1px solid {COLORS['border']};
    border-radius:14px;overflow:hidden">{rows}</div>
    """, unsafe_allow_html=True)
