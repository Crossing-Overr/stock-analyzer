_STORAGE_KEY = "stock_analysator_favorites"


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


# ─── Обёртка над браузерным localStorage ────────────────────────────────────
def _storage():
    # Импортируем лениво, чтобы чистые хелперы тестировались без зависимости.
    from streamlit_local_storage import LocalStorage
    return LocalStorage()


def get_favorites() -> list:
    raw = _storage().getItem(_STORAGE_KEY)
    if not raw:
        return []
    return normalize([s for s in str(raw).split(",")])


def save_favorites(symbols: list) -> None:
    _storage().setItem(_STORAGE_KEY, ",".join(normalize(symbols)))


def add_favorite(symbol: str) -> list:
    updated = add_symbol(get_favorites(), symbol)
    save_favorites(updated)
    return updated


def remove_favorite(symbol: str) -> list:
    updated = remove_symbol(get_favorites(), symbol)
    save_favorites(updated)
    return updated
