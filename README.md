# Investify Analytics v4 — Yahoo-only

Personal stock + options analytics workspace.

## What changed
- Removed Twelve Data entirely.
- Yahoo Finance via yfinance powers stock quotes, history, company stats, fundamentals and options chains.
- Stock Research includes key stats, technical indicators and a transparent rule-based Analyze Setup score.
- Screener includes saved presets, scrollable filters and Best Match.
- Options Lab retains the v3 UI, Greeks, leg cards, payoff chart and dark mode, plus saved presets, scrollable filters and Best Match.
- Watchlist remains browser-local; no login/database required.

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m flask --app app run --port 5050 --debug
```

Open http://127.0.0.1:5050

## Important
Yahoo/yfinance is unofficial and best suited to personal/research use. Availability, quote timing and fields can vary. Best Match and Analyze Setup are transparent rule-based analytics, not personalized investment advice.


## v5 fixed polish
- Fixed the Options Lab JavaScript so all strategy, preset, Find Trades and Best Match buttons respond.
- Stock chart hover shows date/time, price and volume with a crosshair.
- Payoff chart hover shows exact underlying price and P/L.
- Payoff chart marks current spot and breakeven.
- Home page cards navigate to Stock Research, Options Lab, Watchlist, Markets, Screener and Settings.
- Home page shows recent tickers stored locally in the browser.
- Options Best Match now opens the same full Trade Analysis view as clicking a result row.


## v5 cleaned update
- Dark-mode home page readability improved.
- Options vertical strategies include Call Debit, Put Credit, Call Credit, and Put Debit.
- Options single-leg section now includes Covered Call and Cash Secured Put analytics.
- Added Search Beta page and nav link.
- Options filter sidebar remains scrollable.


## Final V5 fixes
- Options vertical strategy grid now shows all four vertical spreads at once: Call Debit, Put Credit, Call Credit, Put Debit.
- Screener filter descriptions added.
- Stock page exchange/market badge fixed so it shows Yahoo exchange text instead of generic "Market".
- Active navbar tab is highlighted, including white text in dark mode.
- Markets page now includes S&P 500, Nasdaq Composite, Dow Jones, Russell 2000, VIX and popular stocks/ETFs.
- Bullish/Bearish direction buttons use green/red active states.


## v6 AI + News backbone
Adds:
- News tab after Stock Research.
- AI Search Beta tab before Settings.
- Finnhub-backed market/company news endpoints.
- Gemini-backed AI summary endpoints.
- Saved AI searches in browser localStorage.
- Same light/dark UI style.

Add these to `.env`:
```bash
FINNHUB_API_KEY=your_finnhub_key_here
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-1.5-flash
```

News headlines require Finnhub. AI summaries require Gemini. If Gemini is missing, the app shows a fallback message instead of crashing.
