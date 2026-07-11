# 📈 Stock Analysator

Веб-приложение для анализа акций US-рынка: тикер → метрики, мультипликаторы,
финансы и **DCF-оценка по трём сценариям** (Bear / Base / Bull).

**Вкладки:** 📊 Анализ · ⚖️ Сравнение · ⭐ Избранное (хранится в браузере).

## Запуск локально

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Откроется на http://localhost:8501

> На этом Mac `pip` и `streamlit` не в PATH — запускай через `python3 -m`.

## Тесты

```bash
python3 -m pytest
```

## Деплой (Streamlit Community Cloud)

1. Запушить репозиторий на GitHub.
2. Зайти на https://share.streamlit.io, подключить репозиторий, указать `app.py`.
3. Получить публичный URL. Каждый `git push` обновляет приложение.

## Структура

```
app.py            вход: конфиг + сайдбар + приветствие
pages/            вкладки Streamlit (Анализ, Сравнение, Избранное)
core/             чистая логика: data, dcf, compare, favorites
ui/               отрисовка: theme, sidebar, components
tests/            pytest для core-логики
```

## Стек

Python · Streamlit (multipage) · yfinance · plotly · pandas · numpy

## Дисклеймер

Только для образовательных целей. Не является инвестиционной рекомендацией.
