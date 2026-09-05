#!/usr/bin/env python3
"""
Генерирует data/sp500.txt — список тикеров S&P 500 с Википедии.
Запуск разово (и когда состав индекса заметно поменяется):
    python3 scripts/fetch_sp500.py
"""
import os
import sys
import urllib.request
import warnings

warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "sp500.txt")
# Википедия блокирует дефолтный User-Agent urllib ("Python-urllib/3.x") 403-м —
# подставляем браузерный, чтобы pandas.read_html вообще смог скачать страницу.
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def main():
    try:
        req = urllib.request.Request(URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read()
        tables = pd.read_html(html)
    except Exception as e:
        print(f"❌ Не удалось получить список с Википедии: {e}")
        print("Проверь интернет или скачай список вручную в data/sp500.txt.")
        sys.exit(1)

    df = tables[0]
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    # yfinance хочет BRK-B вместо BRK.B
    symbols = [str(s).strip().upper().replace(".", "-") for s in df[col] if str(s).strip()]
    symbols = sorted(set(symbols))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(symbols) + "\n")
    print(f"✅ Записано {len(symbols)} тикеров в {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
