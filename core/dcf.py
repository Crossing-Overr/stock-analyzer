from dataclasses import dataclass


@dataclass
class ScenarioResult:
    growth_start: float
    growth_path: list[float]
    fcfs_pv: list[float]
    pv_terminal: float
    enterprise_value: float
    equity_value: float
    intrinsic: float
    tv_share: float


def run_dcf(fcf_base, growth_rates, wacc, terminal_growth, years, shares, net_debt,
            terminal_multiple=None):
    """
    2-фазная DCF с линейным затуханием роста.

    Рост в 1-й год = стартовый (из growth_rates), к последнему году линейно
    спадает к terminal_growth. Это убирает нереалистичное компаундирование и
    не даёт терминальной стоимости раздувать оценку.

    growth_rates: dict {"bear": float, "base": float, "bull": float} —
        стартовые годовые темпы роста FCF.
    terminal_multiple: если задан (>0) — терминальная стоимость считается как
        FCF последнего года × мультипликатор (подход Карлина), а не по формуле
        Гордона. Полезно, потому что Гордон при WACC 10%/росте 2.5% эквивалентен
        всего ≈13.5x FCF, тогда как качественные компании торгуются много дороже.
    Возвращает dict {name: ScenarioResult}.
    """
    # Модель Гордона требует wacc > terminal_growth. Защищаемся от деления
    # на ноль/отрицательного знаменателя, слегка поджимая терминальный рост.
    eff_terminal = min(terminal_growth, wacc - 1e-3)

    results = {}
    for name, g_start in growth_rates.items():
        fcf = fcf_base
        growth_path = []
        fcfs_pv = []
        for y in range(1, years + 1):
            if years > 1:
                g = g_start + (eff_terminal - g_start) * (y - 1) / (years - 1)
            else:
                g = g_start
            growth_path.append(g)
            fcf = fcf * (1 + g)
            fcfs_pv.append(fcf / (1 + wacc) ** y)

        if terminal_multiple and terminal_multiple > 0:
            # Терминал по мультипликатору: «во сколько FCF оценят компанию в конце»
            terminal_value = fcf * terminal_multiple
        else:
            terminal_fcf = fcf * (1 + eff_terminal)
            terminal_value = terminal_fcf / (wacc - eff_terminal)
        pv_terminal = terminal_value / (1 + wacc) ** years

        enterprise_value = sum(fcfs_pv) + pv_terminal
        equity_value = enterprise_value - net_debt
        intrinsic = equity_value / shares if shares > 0 else 0.0
        tv_share = pv_terminal / enterprise_value if enterprise_value > 0 else 0.0

        results[name] = ScenarioResult(
            growth_start=g_start,
            growth_path=growth_path,
            fcfs_pv=fcfs_pv,
            pv_terminal=pv_terminal,
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            intrinsic=intrinsic,
            tv_share=tv_share,
        )
    return results


def dcf_upside_base(fcf_base, price, shares, net_debt,
                    growth_rates, wacc, terminal_growth, years,
                    terminal_multiple=None):
    """
    Апсайд Base-сценария в % ((справедливая - текущая)/текущая), либо None если
    DCF неприменим: нет/отрицательный FCF, нет акций или цены, либо расчётная
    справедливая цена вышла неположительной. Используется в Сравнении и Избранном.
    """
    if not fcf_base or fcf_base <= 0 or not shares or not price or price <= 0:
        return None
    dcf = run_dcf(fcf_base=fcf_base, growth_rates=growth_rates, wacc=wacc,
                  terminal_growth=terminal_growth, years=years,
                  shares=shares, net_debt=net_debt,
                  terminal_multiple=terminal_multiple)
    iv = dcf["base"].intrinsic
    return (iv - price) / price * 100 if iv > 0 else None
