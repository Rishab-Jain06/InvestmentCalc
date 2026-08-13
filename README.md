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


## v7 Gemini + Sentiment
- Gemini calls now use the official REST `generateContent` endpoint directly, so the prior `from google import genai` package/import issue is removed.
- Default model updated to `gemini-3.5-flash` with `gemini-3.6-flash` fallback.
- News page now returns a 0–100 AI news-sentiment score, Bullish/Bearish/Neutral/Mixed label, article counts, confidence, themes, catalysts and risks.
- Stock Research automatically loads recent company-news sentiment with green/red Bullish/Bearish presentation.
- AI Search also shows the sentiment score alongside its brief.
- Sentiment is an AI classification of fetched articles, not a price forecast.

Recommended `.env`:
```bash
FINNHUB_API_KEY=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
```


## v8 AI robustness
- Keeps `gemini-3.5-flash`, which passed the direct connection and sentiment tests.
- Automatically retries malformed Gemini JSON.
- Strips markdown fences and common trailing-comma issues before parsing.
- Uses a stricter second JSON attempt and a final plain-text JSON fallback.
- Moves Stock Research news sentiment to the bottom of the page.
- Removes permanent API-key/setup boxes from News and AI Search.
- Uses cleaner fallback text instead of raw parser errors.


## v9 AI Research Chatbot
- Converts AI Search into a multi-turn AI Research Chat.
- Saves chat threads locally in the browser.
- Supports follow-up questions with conversation history.
- Supports optional ticker context and live stock/news/sentiment context.
- Adds "Ask AI about this trade" from Options Lab full trade analysis.
- Sends selected options trade details to the AI chat as attached context.
- Adds homepage dashboard with S&P 500, Nasdaq, Dow 30, and top market headlines.
- Adds Appearance setting: system/light/dark.


## v10 AI Trade Chat Polish
- Adds Ask AI about this trade and Copy Trade buttons inside the full Options Trade Analysis card.
- Sends full selected trade context into AI Research Chat.
- Improves AI chat output formatting so markdown renders cleanly.
- Adds animated typing dots while Gemini is responding.
- Makes AI answers shorter and more trade-focused by default.
- Adds options-specific quick prompts.
- Makes Stock Research news sentiment manual with an Analyze recent news button instead of auto-running on every stock page load.


## v11 Market Heatmap + Homepage Digest
- Fixes missing Options Trade Analysis buttons by adding visible Ask AI about this trade and Copy Trade buttons.
- Adds robust JS binding so selected trade data is sent to AI Research Chat.
- Adds homepage spacing improvements.
- Adds a 2-line AI Market Context digest on homepage.
- Adds a Finviz-inspired Market Heat Map section to Markets page.
- Heat map supports Mega Cap, Nasdaq, and Dow 30 universes.
- Heat map auto-refreshes every 60 seconds while visible.


## v12 Simple Automatic Sentiment
- Keeps all V11 items:
  - Options Trade Analysis Ask AI + Copy Trade buttons.
  - Robust JS binding for selected trade into AI Research Chat.
  - Homepage spacing improvements.
  - 2-line AI Market Context digest on homepage.
  - Finviz-inspired Market Heat Map on Markets page.
  - Major indices section retained.
  - Mega Cap, Nasdaq, and Dow 30 heat map universes.
  - Heat map auto-refresh every 60 seconds while visible.
- Stock Research sentiment is automatic again, but lightweight.
- Sentiment now analyzes only 5-7 recent headlines for speed.
- Sentiment labels use simple score bands:
  - 75-100 Bullish
  - 60-74 Moderately Bullish
  - 41-59 Neutral
  - 26-40 Moderately Bearish
  - 1-25 Bearish
- News page uses the same simple sentiment score/label concept.

## v13 Sentiment + Heatmap Polish
- Fixes Stock Research sentiment rendering using the working `/api/news/sentiment/<symbol>` JSON.
- Replaces complex sentiment cards with a simple score line: Bearish → Neutral → Bullish.
- Shows only score, label, and a short one-line context note.
- Uses animated three dots for AI loading states instead of visible Loading/Thinking text.
- News page sentiment uses the same simple score-line concept.
- Keeps sentiment lightweight by analyzing a small recent headline set.
- Improves Markets heat map: wider layout, denser tiles, stronger market-cap sizing, muted color scale, and breadth summary.


## v14 AI Chat + Shared Sentiment
- Removed the Markets heat map to keep Markets lightweight and focused.
- Added shared `static/js/sentiment.js` so News and Stock Research use the same sentiment rendering logic.
- Stock Research and News ticker mode now use the same `/api/news/sentiment/<symbol>` endpoint, so the same ticker should show the same score.
- Added Ask AI about this stock from Stock Research.
- Added AI chat rename and delete.
- Added edit last user message and regenerate answer.
- Added Short/Detailed answer style toggle.
- Kept Options Ask AI about this trade and Copy Trade.


## v15 Earnings + Manual Homepage Digest
- Removed Stock Research news sentiment and Stock Research Ask AI button to reduce Gemini quota usage.
- Homepage AI Market Context no longer calls Gemini automatically. It now calls Gemini only when the user clicks Refresh AI digest.
- Homepage digest now shows last updated / last attempt time.
- Removed Edit last message and Regenerate answer buttons from AI Search.
- Kept Gemini usage in AI Chat, Options Ask AI, News, and manual homepage digest.
- Added a simple Stock Research earnings card using Yahoo Finance via yfinance:
  - EPS actual vs. estimate chart
  - recent beat/miss rows
  - simple fallback if earnings data is unavailable.


## v16 Quota-safe AI + Stock AI Button
- Gemini now uses only the configured `GEMINI_MODEL` once instead of trying fallback models, reducing quota burn.
- Added friendly Gemini quota/service messages instead of raw 429/503 JSON.
- Added `Ask AI about this stock` back to Stock Research.
- The Stock Research button does not call Gemini by itself. It only sends context to AI Search; Gemini is called only after the user sends a chat message.
- Kept Stock Research news sentiment removed.
- Kept homepage digest manual-only.


## v17 Header Search + No Earnings
- Removed the Earnings section from Stock Research.
- Removed the earnings backend endpoint and helper module.
- Added a global ticker search bar in the top header/nav.
- Search bar opens `/stock/<TICKER>` and pre-fills the ticker on stock pages.
- Kept V16 quota-safe Gemini behavior.
- Kept Ask AI about this stock button; it only passes context to AI Search and does not call Gemini until a chat message is sent.


## v21 Options Left Panel Only
- Built from the working V17 Options files supplied by the user.
- Changed only the Options left-panel UX plus backend filter correctness.
- Kept the working V17 right-side Candidate Trades / Trade Analysis structure unchanged.
- Moved Find Trades and Best Match to the top under ticker/load.
- Filters are hidden by default behind Show filters.
- Clear filters blanks all filter fields and closes the filter panel.
- Presets now save by name, load from a dropdown, and delete the selected preset.
- Uses new localStorage key `investify_option_presets_v21` to avoid old broken presets.
- Removed the hardcoded 30–45 DTE Put Credit preset button.
- Bullish vertical spreads show Call Debit + Put Credit only.
- Bearish vertical spreads show Call Credit + Put Debit only.
- Vertical delta/IV filters apply to the short leg; min credit applies to final spread net credit.


## v21.1 Options JS Fix
- Fixed Options page JavaScript crash caused by duplicate `OPT_PRESET_KEY` declarations.
- Kept only the v21 preset key: `investify_option_presets_v21`.
- Verified `static/js/options.js` with `node --check`.
- No right-side Options layout changes were made.

## v45 Notes
- Calendar economic events use Investify's curated major U.S. macro event schedule and Alpha Vantage values when an indicator mapping is available.
- Calendar earnings filter is now a clear dropdown: Portfolio, Watchlist, Portfolio + Watchlist, All Earnings, or Custom Symbols.
- Calendar browser/backend cache is 24 hours, with Alpha Vantage macro values cached longer in alpha_vantage_data.py.
- Portfolio holdings are scroll-limited to about 10 visible rows.
- Allocation list is scroll-limited to about 5 visible items and includes a cash toggle.
- Portfolio AI review is shortened to a score, label, headline, and 2-3 bullets.
- Ask AI about portfolio sends portfolio context to AI Search.

## v50 Supabase login setup

Required server environment variables:

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=sb_publishable_or_anon_key
SUPABASE_SERVICE_ROLE_KEY=sb_secret_or_service_role_key
```

Supabase tables expected:

- `profiles`
- `portfolios`
- `holdings`
- `cash_entries`
- `watchlist`
- `user_settings`
- `ai_chats`
- `saved_scans`
- `portfolio_snapshots`

Google OAuth redirects should include:

- `http://127.0.0.1:5050/**`
- `https://investify-analytics.onrender.com/**`

Google OAuth callback in Google Cloud should be your Supabase callback URL:

```text
https://YOUR-PROJECT-REF.supabase.co/auth/v1/callback
```

## v51: Options portfolio tracking + mobile PWA

Run `supabase_v51_option_positions.sql` once in Supabase SQL Editor to enable cloud sync for option positions.

v51 adds:
- Single-leg option tracking: long call, short call, long put, short put.
- Vertical spread tracking: put credit, call credit, put debit, call debit.
- Options positions table on the Portfolio page with current value and P/L.
- Supabase cloud sync for option positions when logged in, with localStorage fallback when logged out.
- Mobile/PWA foundation: service worker, install prompt, manifest shortcuts, and iPhone Add to Home Screen guidance.

The options P/L endpoint uses the existing options chain provider stack. Tradier is used first when configured, with the existing fallback behavior.
