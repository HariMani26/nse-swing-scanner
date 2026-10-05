# Indian Market Trading Copilot

## Trading Workspace

The main menu has Swing Scanner, Intraday Scanner, Live Market Scanner, Watchlist,
Open Positions, and Trade Journal. Stock links open multi-timeframe
evidence with price charts, confirmed pivot trendlines, indicators, score breakdowns,
missing confirmations and structural invalidation levels.

- Timeframes: completed weekly, daily, 4-hour, hourly, 15-minute, 5-minute and 1-minute candles.
  Weekly/4-hour candles are aggregated from provider daily/hourly history. The last NSE
  4-hour session bucket is shorter, ending at 15:30. Incomplete hourly buckets are excluded.
- Qualified results: maximum five BUY, five SELL, and five WATCH stocks. Swing categories
  are Strong Buy, Breakout Buy, Pullback Buy, Reversal Buy, Strong Sell, Breakdown Sell,
  Exit, and No Trade. Exit opens the paper-position workflow; it is not an automatic order.
  Intraday setups include opening-range, previous-day high/low, VWAP, retests, trend
  pullbacks, and high-volume momentum. Daily/hourly decide direction, 15M sets up,
  5M confirms entry, and 1M supplies current price without controlling direction.
- Evidence weights: market alignment 15, weekly structure 15, daily structure 20,
  hourly confirmation 10, volume 10, setup 10, 15M/5M entry 5, reward/risk 10,
  market/sector strength 5. Scores 85+ are A+, 75-84 A, 65-74 watch, below 65 hidden.
  A score never overrides a failed critical gate. Missing confirmations produce only
  watch evidence, never an actionable BUY/SELL. Empty results are NO VALID TRADE SETUP.
- Entry gates require fresh data, aligned market/sector/timeframes, volume and at least 2R.
  Liquidity minimums are 20-day average turnover INR 10 crore and 100,000 shares/day.
  The entry zone is +/- 0.05 ATR around the observed price; reward/risk uses its worst entry.
  Elevated available INDIA VIX (25+) triggers a conservative risk-off filter.
- Both swing directions require weekly/daily/hourly/15M/5M agreement. EMA200 must be
  available on weekly/daily for swing and daily for intraday. Missing index/VIX/breadth,
  unknown or wide spreads, stale prices, false breaks, and excessive extension block entries.
  Sideways markets require exceptional 85+ evidence, sector strength, and 1.5x volume.
  Opposing daily/weekly pivots constrain Target 1; absent pivots, 2R/3R targets are
  calculated projections, not observed resistance/support or promised outcomes.
- Indicators include EMA9/20/50/200, RSI14, MACD, ATR, session VWAP, relative volume
  against the preceding 20 bars, and 20-session relative return versus NIFTY. VWAP is
  candle-derived, not an exchange tick VWAP. Sector indices are broad Yahoo metadata
  proxies, not verified official sector membership. Missing sector data blocks confirmation.
- Price-action fields use confirmed pivots and completed candles: structure breaks,
  character changes, sweeps, false breaks, retests, and pivot/ATR zones. These are
  deterministic heuristics, not proof of institutional activity or tested profitability.

### Data And Coverage Limits

Yahoo is a delayed, best-effort free provider, **not a one-second live feed**. Detailed
analysis automatically requests refreshes at the provider's 60-second interval; batch jobs may
take longer. Daily/hourly history has 15/5-minute caches. No synthetic ticks are created.
The application shows **REAL-TIME DATA UNAVAILABLE** and disables all confirmed
signals and live alerts unless a real-time-capable provider is implemented and connected.
No such real-time adapter is included in this version. Prices older than 120 seconds
cannot enable a current setup. Data errors remove actionable levels. The weekday
session clock does not include exchange holidays or special sessions.

NSE stock symbols come from the online Upstox JSON catalogue, never local CSV/Excel.
Nifty 50/100/500 membership is requested separately from NSE's current Market Watch JSON
endpoint (`marketWatchApi`, `getIndicesData`) and is never inferred from the full catalogue.
The nested response is checked for the requested index and its full constituent count;
network failures or incomplete lists show an explicit error without a CSV fallback.
Qualified scans default to the complete active online NSE catalogue. Daily liquidity/history
is screened in batches of 25, followed by detailed batches of 10 for every eligible stock.
Nothing is truncated to the first page or first five symbols before qualification. Progress
reports the current phase, processed count and exclusions. Large scans can take substantial
time and incur provider rate limits; the 60-second refresh interval is not a latency promise.
Stale candidates lose their confirmed state before ranking and again before API/display use.
Inactive user-removed symbols are excluded; coverage is the active catalogue, not a claim
that every listed NSE instrument is available from Yahoo.

The market filter requests NIFTY 50/100/500, BANK NIFTY and India VIX. Breadth is explicitly
completed-daily advances minus declines as a percentage of covered stocks, not live exchange
breadth. It requires at least 80% coverage and reports its sample counts. Missing provider
index data blocks qualification. The legacy daily/weekly overview endpoint remains for compatibility.

### Risk And Paper Journal

Default capital is INR 300,000, per-trade risk 0.5% (maximum 1%), allocation ceiling
INR 300,000. Quantity is the smaller of risk-budget and cash-budget quantities, including
reserved capital and a 2% total open-position risk cap. Risk preferences are local to
the browser; the server validates every submitted paper entry. No leverage, martingale
or automatic capital escalation is used. Stop-loss gaps/slippage may exceed planned loss.

Open Positions and Trade History are **manual paper records only**, persisted in SQLite.
Entries require explicit acknowledgement, valid active NSE symbols, cash/risk limits and
at least 2R. Maximum three simultaneous positions; overlapping or unknown sector exposure
requires a separate explicit acknowledgement. This is a sector-concentration warning, not
a computed pairwise correlation model. Overnight cash-equity shorts are rejected. Exits use the manually supplied
price and produce gross P&L, excluding fees/taxes. No broker connection or order is placed.

In-app alerts cover EARLY WATCH, CONFIRMATION, ENTRY, INVALIDATED, TARGET 1, TARGET 2,
and STOP LOSS. Setup alerts occur on state changes, not repeated identical polls;
paper target/stop alerts are persisted once per position/event. Price crossing detection
uses provider snapshots, not tick-by-tick execution. Setup transition baselines are
in-process and reset on server restart. Scans run only while a view is monitored, not
as an independent background push service. With Yahoo, live alerts remain disabled.

New API routes are under `/api/trading`: `/screen`, `/market`, `/alerts`, `/risk/size`,
`/positions`, and `/positions/{id}/close`. The older scanner API remains for compatibility;
its legacy score and mock-news option are not used by the new trading workspace.
Use this unauthenticated, single-user API locally; add authentication before exposing it.

The sections below describe the original scanner setup and legacy API behavior.

A personal-use technical screening tool for Indian (NSE) swing trading. It scans a
configurable universe of stocks, computes standard technical indicators, and produces a
transparent 0-100 score with a plain-English explanation of *why* a stock was
shortlisted.

> **This tool does not predict the market and does not guarantee profits.**
> Every score, label ("STRONG SWING CANDIDATE", "WATCH", etc.) and trade idea is a
> **screening result, not financial advice**. Always do your own research.
> All market data is labeled with its source and timestamp, and mock/demo data is
> clearly marked as such everywhere it appears in the UI.

---

## Contents

1. [Installation](#1-installation)
2. [Environment variables](#2-environment-variables)
3. [Online stock universe](#3-online-stock-universe)
4. [Configuring the market-data provider](#4-configuring-the-market-data-provider)
5. [Configuring the news provider](#5-configuring-the-news-provider)
6. [How scoring works](#6-how-scoring-works)
7. [Running the backend](#7-running-the-backend)
8. [Running the frontend](#8-running-the-frontend)
9. [Running the tests](#9-running-the-tests)
10. [Limitations of free market data](#10-limitations-of-free-market-data)
11. [Project structure](#11-project-structure)
12. [Docker](#12-docker)
13. [Security notes](#13-security-notes)

---

## 1. Installation

Prerequisites:
- Python 3.11+
- Node.js 18+ (tested with Node 20/24)
- (Optional) Docker + Docker Compose

Clone/open the project, then:

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

Copy the environment templates:

```powershell
copy .env.example .env                 # root -> backend config (used by docker-compose)
copy backend\.env.example backend\.env  # if running backend directly, .env.example at repo root works too
copy frontend\.env.example frontend\.env
```

The backend reads `backend/.env` (via `python-dotenv`/`pydantic-settings`) when run
locally. When running through Docker Compose, the root `.env` is passed to the backend
container via `env_file`.

## 2. Environment variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLite connection string (default `sqlite:///./data/nse_scanner.db`) |
| `MARKET_DATA_PROVIDER` | `mock` (default, no network) or `yfinance` (free, delayed) |
| `MARKET_DATA_API_KEY` | Reserved for a future paid/real-time provider - **never sent to the frontend** |
| `NEWS_PROVIDER` | `mock` (default) or `rss` (free Google News RSS, best-effort) |
| `NEWS_API_KEY` | Reserved for a future licensed news provider |
| `CACHE_TTL_SECONDS` | How long cached market data / news is considered fresh |
| `RATE_LIMIT_MAX_CALLS` / `RATE_LIMIT_PERIOD_SECONDS` | Outbound request rate limit for real providers |
| `SCAN_SCHEDULE_HOUR` / `SCAN_SCHEDULE_MINUTE` / `SCAN_TIMEZONE` | Daily automatic scan schedule (default 16:00 IST, after market close) |
| `ENABLE_SCHEDULER` | Set `false` to disable the background scheduler |
| `MARKET_OPEN_TIME` / `MARKET_CLOSE_TIME` | Used to compute the OPEN/CLOSED badge |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |

The frontend only reads `VITE_API_BASE_URL` (see `frontend/.env.example`). **No API
keys are ever read by or exposed to the frontend.**

## 3. Online stock universe

Stock symbols and company names are downloaded from Upstox's public NSE instrument
catalogue: `https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz`.
This is a JSON API asset, not an Excel or CSV import. No login or API key is needed.
Only records with segment `NSE_EQ` and instrument types `EQ` (equities), `BE`
(trade-to-trade equities), or `RR` (REITs) are used; derivatives and other instrument
types are excluded. Catalogue inclusion does not establish intraday eligibility;
trade-to-trade instruments require delivery settlement. The catalogue does not supply sectors.

The backend synchronizes the catalogue at startup and checks for a refresh when
the stock list is opened or a real-data scan begins, with a 24-hour cache. The
Watchlist page provides search, 50-row pages, stock-analysis links, sync status,
and a refresh icon (requests limited to once per five minutes).

Existing matching CSV entries are migrated to online metadata and activated. CSV-only entries
absent from the catalogue are retired after a successful sync and excluded from
listing/scanning. Manual entries and disabled existing online stocks are preserved. A failed
or suspiciously incomplete download does not wipe the database; the page reports
the failure and retains previously downloaded online data. An empty installation
stays empty until a successful download. There is no local-file fallback.

CSV import is no longer registered in the API or application navigation. Legacy
sample files and parser tests remain on disk but are not used by the running app.
The instrument catalogue is a daily directory, not streaming prices. Individual
stock quotes use the separate delayed Yahoo feed described below. A full-market
scan can take substantially longer and encounter free-provider rate limits.

## 4. Configuring the market-data provider

Market data access is behind the `MarketDataProvider` interface
(`backend/app/services/market_data/base.py`) so a new source can be added without
touching the rest of the app.

- **`mock`** (default): deterministic synthetic OHLCV data seeded from the symbol name.
  No network access, no API key, safe to run anywhere. Always labeled `mock`/"demo data"
  in the UI.
- **`yfinance`**: free, delayed data from Yahoo Finance via the unofficial `yfinance`
  package (NSE symbols are queried as `SYMBOL.NS`). Requests are batched, cached in
  SQLite, rate-limited, and retried with exponential backoff
  (`backend/app/services/market_data/yfinance_provider.py`).

To switch: set `MARKET_DATA_PROVIDER=yfinance` in `.env` and restart the backend.

### Stock quotes and daily trend signals

Open a stock from the Watchlist for its latest Yahoo one-minute candle price,
refreshed every 60 seconds while the page is visible and auto-refresh is enabled.
This is unofficial, delayed, best-effort data, not a tick feed or a guaranteed
real-time API. No API key is required. Requests are cached for 60 seconds across
clients; failures retain the last quote and its original timestamp with a stale
warning. During weekday trading hours a quote older than two minutes is marked
stale. Outside those hours the last session quote is shown, and quotes older than
four days are marked stale. Trading-hours status does not include exchange holidays.

The daily chart marks confirmed HH (higher high), HL (higher low), LH (lower high),
and LL (lower low) pivots. A pivot needs three completed candles on each side;
equal plateaus are not counted. Lines connect the last two confirmed highs/lows,
not forecast price paths. Daily data is cached separately from quotes for the
configured `CACHE_TTL_SECONDS` (default 900 seconds).

- BUY: higher highs and higher lows, a new daily close crossing above the latest
  confirmed swing high, and volume at least 1.2 times the prior 20-day average.
- SELL: lower highs and lower lows, a new daily close crossing below the latest
  confirmed swing low, and the same volume confirmation. This is a bearish/exit
  screening signal, not an instruction or automated short-sale order.
- WAIT: no confirmed crossover, insufficient/invalid data, or history over seven
  calendar days old. A stale daily-history warning is shown when applicable.

Signals use completed weekday daily candles only; today's candle is admitted
after 16:00 IST to allow for publication after the close. Special weekend exchange
sessions are not supported. Displayed signal close, support/ATR stop, and 2R target
are historical setup levels, not executable live quotes or guaranteed returns.
News remains independently configured by `NEWS_PROVIDER`; mock news is demo data.

To add a real/paid provider later: implement `MarketDataProvider.get_daily_history()`
and `get_index_quote()` in a new module, then add a branch in
`backend/app/services/market_data/factory.py`. Store any API key only in `.env`
(`MARKET_DATA_API_KEY`) - never in frontend code.

## 5. Configuring the news provider

News access is behind the `NewsProvider` interface
(`backend/app/services/news/base.py`):

- **`mock`** (default): deterministic sample headlines, clearly labeled
  `Demo News Wire (mock)`. About 1 in 6 symbols intentionally has no headlines, to
  exercise the "News data unavailable" path.
- **`rss`**: free public Google News RSS search per symbol/company name
  (`backend/app/services/news/rss_provider.py`). Best-effort and unofficial - if the
  request fails or returns nothing, the app reports "News data unavailable" rather than
  fabricating a sentiment.

Sentiment is derived with a small, transparent keyword classifier
(`backend/app/services/news/sentiment.py`) - not a black-box ML model - so every
sentiment label can be explained. **The app never invents headlines or a sentiment
score when no reliable news is available.**

To switch: set `NEWS_PROVIDER=rss` in `.env`. To add a licensed news API later,
implement `NewsProvider.get_news()` in a new module and register it in
`backend/app/services/news/factory.py`.

## 6. How scoring works

Every scan produces a transparent score from **0-100**:

| Component | Max points |
|---|---|
| Technical | 70 |
| News | 20 |
| Market/sector | 10 |

**Technical (70):**
- EMA trend (15): full points if `price > EMA20 > EMA50`; partial if price is above
  EMA20 but EMA20 is still below EMA50; small credit for a pullback below EMA20 within
  a larger EMA20>EMA50 uptrend; zero if price is below both EMAs.
- RSI (10): 60-70 = strong momentum (full points), 50-60 = positive, >70 = extended
  (partial credit + an "overbought" warning, never auto-rejected), 40-50 = neutral,
  30-40 = weak, <30 = oversold/possible reversal (flagged, not an automatic buy).
- MACD (15): +8 if MACD > signal, +4 more if MACD > 0, +3 more if the histogram is
  increasing; 0 if MACD < signal.
- Volume (15): scored by the ratio of current volume to the 20-day average - higher
  ratio = higher score; below-average volume scores low even on a price breakout.
- Breakout / 52-week high (10): full points only for a **confirmed daily-close**
  breakout above recent resistance (never an intraday spike); partial credit for being
  within 3-7% of the 52-week high.
- Support/resistance (5): credit for being positioned near an identified swing-based
  support/resistance zone.

**News (20):** +20 strongly positive, +10 positive, 0 neutral/no meaningful news, -10
negative, -20 strongly negative. If news is unavailable, the contribution is 0 and the
UI shows "News data unavailable" - never a fabricated score.

**Market/sector (10):** +10 bullish, +5 neutral, 0 bearish, based on NIFTY 50 / NIFTY
500 trend. If the market trend is strongly bearish, the **final score is additionally
reduced** (a 15% dampening) on top of the 0-point market component.

**Labels** (screening results, not financial advice):
- `80-100` → STRONG SWING CANDIDATE
- `65-79` → WATCH
- `50-64` → NEUTRAL
- `<50` → AVOID / WEAK SETUP

**Risk/reward** (only for stocks with a detected breakout or pullback setup):
- Breakout: entry above confirmed resistance; stop loss based on recent support/ATR;
  targets at 1:2 and 1:3 risk/reward.
- Pullback: entry near support/EMA20; stop loss below support (with an ATR buffer);
  target uses resistance and a minimum 1:2 risk/reward.
- If the resulting risk/reward is below **1:1.5**, no entry/stop/targets are shown at
  all - the app never forces a trade idea onto a poor setup.

All scoring logic lives in `backend/app/services/scanner/` (`scoring.py`,
`breakout.py`, `risk_reward.py`) and is unit-tested in `backend/tests/`.

## 7. Running the backend

```powershell
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

On startup the backend creates the SQLite database, synchronizes the online NSE
JSON instrument catalogue, and starts the daily scan scheduler (unless
`ENABLE_SCHEDULER=false`). API docs are available at `http://localhost:8000/docs`.

Trigger a scan manually:

```powershell
curl -X POST http://localhost:8000/api/scan/run
```

## 8. Running the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Make sure the backend is running and
`VITE_API_BASE_URL` (in `frontend/.env`) points to it (default
`http://localhost:8000/api`).

## 9. Running the tests

```powershell
cd backend
.\.venv\Scripts\activate
pytest -q
```

Tests cover: EMA/RSI/MACD/ATR indicator calculations, the scoring engine, risk/reward
calculation (including the "no trade if RR is poor" rule), breakout/pullback detection
(daily-close-only confirmation), CSV import (flexible mapping, add/replace modes,
missing symbol column), missing/insufficient market data handling (scan never crashes),
news provider behavior (deterministic mock data, "unavailable" contract, sentiment
classification), and the async rate limiter used by real providers.

## 10. Limitations of free market data

- **Mock data is synthetic** - it is generated for demo purposes and does not reflect
  real prices, volumes, or news. It is always labeled `mock`/"demo data" in the UI.
- **`yfinance` data is free, unofficial, and delayed** - Yahoo Finance is not an
  official NSE data vendor, does not guarantee uptime or accuracy, and may rate-limit
  or block requests without notice. It is not suitable for real-time trading decisions.
- **The Google News RSS provider is best-effort** - it is a public search feed, not a
  licensed news API, and coverage/completeness is not guaranteed. Missing news is
  reported honestly as "News data unavailable" rather than guessed.
- **This is a personal screening tool**, not a broker-connected trading system. It does
  not place orders, does not handle broker credentials, and does not guarantee any
  outcome. Always verify data independently before making trading decisions.

## 11. Project structure

```
/backend
  /app
    api/            FastAPI routers (dashboard, stocks, scan, csv, market)
    services/
      market_data/  Provider interface + mock/yfinance implementations
      indicators/   EMA/RSI/MACD/ATR/support-resistance calculations (pandas + ta)
      scanner/      Scoring engine, breakout/pullback detection, risk/reward
      news/         Provider interface + mock/RSS implementations, sentiment
      market_context/  NIFTY 50/500 trend determination
      csv_import/   Flexible CSV parsing + column mapping + universe import
      cache/        Caching layers in front of market data / news providers
    models.py, schemas.py, database.py, config.py, scheduler.py, seed.py, main.py
  /data             Seed CSVs (52WeekHigh.csv, nifty500.csv)
  /tests            pytest test suite
/frontend
  /src
    api/            Typed fetch client
    components/      Reusable UI (tables, filters, charts, badges, ...)
    pages/           Dashboard, StockDetail, Watchlist, CsvImport
    types/           Shared TypeScript types mirroring backend schemas
/docker-compose.yml
/.env.example
```

## 12. Docker

```powershell
docker compose up --build
```

- Backend: `http://localhost:8000` (API docs at `/docs`)
- Frontend: `http://localhost:3000` (nginx serves the built SPA and proxies `/api/*`
  to the backend container)

The SQLite database is persisted to `./backend/data` via a bind mount.

## 13. Security notes

- No broker integration, no automatic order placement, no handling of broker
  passwords.
- API keys (for future real providers) are read only from backend `.env` and are never
  exposed to the frontend bundle.
- CORS is restricted to the origins listed in `CORS_ORIGINS`.
- Legacy CSV parsing tests use pandas; the running API does not expose CSV import. Column mapping is explicit and
  user-controlled rather than inferred from untrusted free-text execution.
