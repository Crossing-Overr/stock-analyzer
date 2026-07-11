import streamlit as st

_SESSION_KEY = "favorites"


def normalize(symbols) -> list:
    """Upper-case, обрезать пробелы, выкинуть пустые, убрать дубли, сохранить порядок."""
    if not symbols:
        return []
    seen = set()
    out = []
    for s in symbols:
        if not s:
            continue
        sym = str(s).strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def add_symbol(symbols: list, symbol: str) -> list:
    return normalize(list(symbols) + [symbol])


def remove_symbol(symbols: list, symbol: str) -> list:
    target = str(symbol).strip().upper()
    return [s for s in normalize(symbols) if s != target]


# ─── Хранилище на время сессии (st.session_state) ───────────────────────────
# Пока держим избранное в состоянии сессии Streamlit: надёжно и без внешних
# зависимостей. Избранное живёт, пока открыта вкладка. Постоянное хранение в
# браузере (localStorage, переживает перезагрузку) — следующий шаг; интерфейс
# этих функций менять не придётся.
def get_favorites() -> list:
    return normalize(st.session_state.get(_SESSION_KEY, []))


def save_favorites(symbols: list) -> None:
    st.session_state[_SESSION_KEY] = normalize(symbols)


def add_favorite(symbol: str) -> list:
    updated = add_symbol(get_favorites(), symbol)
    save_favorites(updated)
    return updated


def remove_favorite(symbol: str) -> list:
    updated = remove_symbol(get_favorites(), symbol)
    save_favorites(updated)
    return updated
