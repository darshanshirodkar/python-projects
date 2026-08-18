import os
import time
from datetime import datetime, timezone
import sqlite3
import yfinance as yf
from flask import Flask, jsonify, request, render_template, g

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio.db")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL UNIQUE,
            quantity REAL NOT NULL DEFAULT 0,
            avg_cost REAL NOT NULL DEFAULT 0,
            custom_tax_rate REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('BUY','SELL')),
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            price_usd REAL NOT NULL,
            fx_rate REAL,
            realized_gain REAL,
            timestamp TEXT NOT NULL
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    # Initialize default global tax rate if not present
    cursor.execute("SELECT value FROM settings WHERE key = 'global_tax_rate'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (key, value) VALUES ('global_tax_rate', '15.0')")

    # Dynamic schema migrations
    cursor.execute("PRAGMA table_info(positions)")
    pos_cols = [row[1] for row in cursor.fetchall()]
    if "custom_tax_rate" not in pos_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN custom_tax_rate REAL")

    cursor.execute("PRAGMA table_info(transactions)")
    tx_cols = [row[1] for row in cursor.fetchall()]
    if "currency" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD'")
    if "price_usd" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN price_usd REAL")
        cursor.execute("UPDATE transactions SET price_usd = price WHERE price_usd IS NULL")
    if "fx_rate" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN fx_rate REAL")

    db.commit()
    db.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Price & FX helpers
# ---------------------------------------------------------------------------

_price_cache = {}
_CACHE_TTL_SECONDS = 30


def fetch_usdinr_rate():
    # Helper to directly fetch USD to INR exchange rate
    cached = _price_cache.get("USDINR=X")
    if cached and (time.time() - cached[1]) < _CACHE_TTL_SECONDS:
        return cached[0]

    t = yf.Ticker("USDINR=X")
    price = None
    try:
        fast = t.fast_info
        price = fast.get("last_price") or fast.get("lastPrice")
    except Exception:
        price = None

    if price is None:
        hist = t.history(period="1d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])

    if not price:
        price = 83.5  # Fallback rate if market data fails

    price = float(price)
    _price_cache["USDINR=X"] = (price, time.time())
    return price


def fetch_price_usd(ticker):
    cached = _price_cache.get(ticker)
    if cached and (time.time() - cached[1]) < _CACHE_TTL_SECONDS:
        return cached[0]

    t = yf.Ticker(ticker)
    price = None
    currency = "USD"

    try:
        fast = t.fast_info
        price = fast.get("last_price") or fast.get("lastPrice")
        currency = fast.get("currency", "USD") or "USD"
    except Exception:
        price = None

    if price is None:
        hist = t.history(period="1d")
        if hist.empty:
            raise ValueError(f"Could not fetch price for '{ticker}'")
        price = float(hist["Close"].iloc[-1])
        try:
            currency = t.info.get("currency", "USD") or "USD"
        except Exception:
            currency = "USD"

    price = float(price)

    # Convert ticker quote currency to USD if it is in INR
    if currency.upper() == "INR":
        usdinr = fetch_usdinr_rate()
        if usdinr and usdinr > 0:
            price = price / usdinr

    _price_cache[ticker] = (price, time.time())
    return price


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/settings", methods=["GET"])
def get_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return jsonify({row["key"]: row["value"] for row in rows})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(force=True, silent=True) or {}
    db = get_db()
    
    if "global_tax_rate" in data:
        try:
            val = float(data["global_tax_rate"])
            if val < 0 or val > 100:
                return jsonify({"error": "Tax rate must be between 0 and 100"}), 400
            db.execute(
                "INSERT INTO settings (key, value) VALUES ('global_tax_rate', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(val),),
            )
            db.commit()
        except ValueError:
            return jsonify({"error": "Invalid tax rate value"}), 400

    return jsonify({"status": "ok"})


@app.route("/api/positions", methods=["GET"])
def list_positions():
    db = get_db()
    rows = db.execute("SELECT * FROM positions ORDER BY ticker").fetchall()
    
    try:
        usdinr = fetch_usdinr_rate()
    except Exception:
        usdinr = 1.0

    result = []
    for row in rows:
        entry = dict(row)
        try:
            price_usd = fetch_price_usd(row["ticker"])
            cost_basis_usd = row["avg_cost"] * row["quantity"]
            market_value_usd = price_usd * row["quantity"]
            unrealized_gain_usd = market_value_usd - cost_basis_usd

            entry["current_price"] = price_usd
            entry["market_value"] = market_value_usd
            entry["cost_basis"] = cost_basis_usd
            entry["unrealized_gain"] = unrealized_gain_usd
            entry["unrealized_gain_pct"] = (
                (unrealized_gain_usd) / cost_basis_usd * 100 if cost_basis_usd else 0
            )

            # INR equivalents for display
            entry["current_price_inr"] = price_usd * usdinr
            entry["market_value_inr"] = market_value_usd * usdinr
            entry["cost_basis_inr"] = cost_basis_usd * usdinr
            entry["unrealized_gain_inr"] = unrealized_gain_usd * usdinr
            entry["price_error"] = None
        except Exception as e:
            entry["current_price"] = None
            entry["market_value"] = None
            entry["cost_basis"] = row["avg_cost"] * row["quantity"]
            entry["unrealized_gain"] = None
            entry["unrealized_gain_pct"] = None
            entry["price_error"] = str(e)
        result.append(entry)
    return jsonify(result)


@app.route("/api/position/<int:position_id>/tax_rate", methods=["PATCH"])
def update_position_tax_rate(position_id):
    data = request.get_json(force=True, silent=True) or {}
    rate_val = data.get("custom_tax_rate")

    custom_rate = None
    if rate_val is not None and rate_val != "":
        try:
            custom_rate = float(rate_val)
            if custom_rate < 0 or custom_rate > 100:
                return jsonify({"error": "Tax rate must be between 0 and 100"}), 400
        except ValueError:
            return jsonify({"error": "Invalid tax rate"}), 400

    db = get_db()
    db.execute(
        "UPDATE positions SET custom_tax_rate = ?, updated_at = ? WHERE id = ?",
        (custom_rate, now_iso(), position_id),
    )
    db.commit()
    return jsonify({"status": "ok", "custom_tax_rate": custom_rate})


@app.route("/api/transaction", methods=["POST"])
def add_transaction():
    data = request.get_json(force=True, silent=True) or {}
    ticker = (data.get("ticker") or "").strip().upper()
    action = (data.get("action") or "").strip().upper()
    currency = (data.get("currency") or "USD").strip().upper()

    try:
        quantity = float(data.get("quantity"))
        price_input = float(data.get("price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Quantity and price must be numbers"}), 400

    if not ticker:
        return jsonify({"error": "Ticker is required"}), 400
    if action not in ("BUY", "SELL"):
        return jsonify({"error": "Action must be BUY or SELL"}), 400
    if currency not in ("USD", "INR"):
        return jsonify({"error": "Currency must be USD or INR"}), 400
    if quantity <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400
    if price_input < 0:
        return jsonify({"error": "Price must be non-negative"}), 400

    fx_rate = 1.0
    price_usd = price_input

    if currency == "INR":
        try:
            usdinr = fetch_usdinr_rate()
            if not usdinr or usdinr <= 0:
                raise ValueError("Invalid FX rate returned")
            fx_rate = usdinr
            price_usd = price_input / usdinr
        except Exception as e:
            return jsonify({"error": f"Failed to fetch USD/INR rate: {str(e)}"}), 400

    try:
        fetch_price_usd(ticker)
    except Exception:
        return jsonify({"error": f"Could not validate ticker '{ticker}'. Check symbol."}), 400

    db = get_db()
    existing = db.execute("SELECT * FROM positions WHERE ticker = ?", (ticker,)).fetchone()
    realized_gain = None
    ts = now_iso()

    if action == "BUY":
        if existing:
            old_qty = existing["quantity"]
            old_cost = existing["avg_cost"]
            new_qty = old_qty + quantity
            new_avg_cost = ((old_qty * old_cost) + (quantity * price_usd)) / new_qty
            db.execute(
                "UPDATE positions SET quantity=?, avg_cost=?, updated_at=? WHERE id=?",
                (new_qty, new_avg_cost, ts, existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO positions (ticker, quantity, avg_cost, created_at, updated_at) "
                "VALUES (?,?,?,?,?)",
                (ticker, quantity, price_usd, ts, ts),
            )
    else:  # SELL
        available = existing["quantity"] if existing else 0
        if not existing or quantity > available + 1e-9:
            return jsonify(
                {"error": f"Cannot sell {quantity} shares of {ticker}; only {available} held."}
            ), 400

        realized_gain = (price_usd - existing["avg_cost"]) * quantity
        new_qty = available - quantity
        if new_qty <= 1e-9:
            db.execute("DELETE FROM positions WHERE id=?", (existing["id"]),)
        else:
            db.execute(
                "UPDATE positions SET quantity=?, updated_at=? WHERE id=?",
                (new_qty, ts, existing["id"]),
            )

    db.execute(
        "INSERT INTO transactions (ticker, action, quantity, price, currency, price_usd, fx_rate, realized_gain, timestamp) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (ticker, action, quantity, price_input, currency, price_usd, fx_rate, realized_gain, ts),
    )
    db.commit()
    return jsonify({"status": "ok", "realized_gain": realized_gain})


@app.route("/api/transactions", methods=["GET"])
def list_transactions():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM transactions ORDER BY timestamp DESC, id DESC LIMIT 200"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/position/<int:position_id>", methods=["DELETE"])
def delete_position(position_id):
    db = get_db()
    db.execute("DELETE FROM positions WHERE id=?", (position_id,))
    db.commit()
    return jsonify({"status": "ok"})


@app.route("/api/summary", methods=["GET"])
def summary():
    db = get_db()

    rate_param = request.args.get("tax_rate")
    if rate_param is not None:
        try:
            global_tax_rate = float(rate_param)
        except ValueError:
            return jsonify({"error": "tax_rate must be a number"}), 400
    else:
        setting_row = db.execute("SELECT value FROM settings WHERE key = 'global_tax_rate'").fetchone()
        global_tax_rate = float(setting_row["value"]) if setting_row else 15.0

    if global_tax_rate < 0 or global_tax_rate > 100:
        return jsonify({"error": "tax_rate must be between 0 and 100"}), 400

    rows = db.execute("SELECT * FROM positions").fetchall()

    total_market_value_usd = 0.0
    total_cost_basis_usd = 0.0
    total_unrealized_gain_usd = 0.0
    total_tax_owed_usd = 0.0
    errors = []

    for row in rows:
        try:
            price = fetch_price_usd(row["ticker"])
        except Exception as e:
            errors.append({"ticker": row["ticker"], "error": str(e)})
            continue

        market_value = price * row["quantity"]
        cost_basis = row["avg_cost"] * row["quantity"]
        unrealized_gain = market_value - cost_basis

        total_market_value_usd += market_value
        total_cost_basis_usd += cost_basis
        total_unrealized_gain_usd += unrealized_gain

        pos_tax_rate = (
            row["custom_tax_rate"]
            if (row["custom_tax_rate"] is not None)
            else global_tax_rate
        )
        taxable_gain = max(unrealized_gain, 0.0)
        total_tax_owed_usd += taxable_gain * (pos_tax_rate / 100.0)

    value_after_tax_usd = total_market_value_usd - total_tax_owed_usd

    try:
        usdinr = fetch_usdinr_rate()
    except Exception:
        usdinr = None

    def to_inr(x):
        return x * usdinr if (usdinr is not None and x is not None) else None

    result = {
        "global_tax_rate": global_tax_rate,
        "usdinr_rate": usdinr,
        "usd": {
            "total_cost_basis": total_cost_basis_usd,
            "value_before_tax": total_market_value_usd,
            "unrealized_gain": total_unrealized_gain_usd,
            "tax_owed": total_tax_owed_usd,
            "value_after_tax": value_after_tax_usd,
        },
        "inr": {
            "total_cost_basis": to_inr(total_cost_basis_usd),
            "value_before_tax": to_inr(total_market_value_usd),
            "unrealized_gain": to_inr(total_unrealized_gain_usd),
            "tax_owed": to_inr(total_tax_owed_usd),
            "value_after_tax": to_inr(value_after_tax_usd),
        },
        "errors": errors,
    }
    return jsonify(result)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)