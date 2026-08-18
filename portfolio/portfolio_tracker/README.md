# Ledger — Portfolio Tracker

A small Flask + SQLite web app to track a stock portfolio: add/reduce positions,
pull live prices, and see portfolio value before/after capital gains tax in
USD and INR.

## Setup

```bash
cd portfolio_tracker
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in your browser. A `portfolio.db` SQLite file
is created automatically on first run in the same folder.

## How it works

- **Add a position (Buy):** enter ticker, quantity, and the price you paid
  per share. If you already hold that ticker, your average cost basis is
  recalculated as a quantity-weighted average.
- **Subtract from a position (Sell):** enter the ticker, quantity to sell,
  and the sale price. This reduces (or fully removes) the position and logs
  the realized gain/loss for that sale in the transaction history. You can't
  sell more shares than you hold.
- **Live prices:** current prices are fetched via [`yfinance`](https://pypi.org/project/yfinance/),
  which requires no API key. Prices are cached for 30 seconds to avoid
  hammering the API on every page refresh.
- **Tax rate:** enter a capital gains tax rate (%). It's applied only to the
  portfolio's *net unrealized gain* (current market value minus cost basis).
  If the portfolio is at a net loss, no tax is applied. This is a simple
  approximation, not tax advice — real capital gains rules (short vs. long
  term, per-lot treatment, realized vs. unrealized, etc.) vary by
  jurisdiction.
- **USD / INR:** all prices and cost inputs are assumed to be in USD. The
  live USD→INR exchange rate (via the `USDINR=X` ticker) is used only to
  translate the portfolio totals for display — it doesn't affect the
  underlying USD figures.

## Notes & things you may want to extend

- Tickers are validated against Yahoo Finance at the time you submit a
  transaction (so a typo like `AAPLE` will be rejected).
- The `/api/transactions` endpoint returns your full buy/sell log — useful
  if you want to export or audit history later.
- If you hold non-US tickers priced in another currency (e.g. `TCS.NS` on
  the NSE, quoted in INR), the app will still fetch and display a price for
  them, but the tax/summary math assumes everything is USD — you'd want to
  extend `fetch_price_usd` to detect and convert per-ticker currency before
  relying on it for those.
- No authentication — this is meant to run locally for personal use. Don't
  expose it directly to the internet as-is.

## Project structure

```
portfolio_tracker/
├── app.py                 # Flask app: routes, SQLite schema, price fetching
├── requirements.txt
├── templates/
│   └── index.html         # Dashboard markup
├── static/
│   ├── style.css          # Terminal/ticker-inspired design
│   └── app.js             # Frontend logic (fetch, render, forms)
└── portfolio.db           # created automatically on first run
```
