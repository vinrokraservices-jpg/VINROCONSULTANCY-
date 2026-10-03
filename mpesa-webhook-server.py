import os
import sqlite3
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

TILL_NUMBER = os.getenv("MPESA_SHORTCODE", "7599910")
DB_PATH = os.getenv("DB_PATH", "/data/mpesa_payments.db")
WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY", "")

_db_lock = threading.Lock()


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trans_id TEXT UNIQUE NOT NULL,
                transaction_type TEXT,
                trans_time TEXT,
                trans_amount REAL,
                business_short_code TEXT,
                bill_ref_number TEXT,
                invoice_number TEXT,
                org_account_balance TEXT,
                third_party_trans_id TEXT,
                msisdn TEXT,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                raw_json TEXT NOT NULL,
                received_at TEXT NOT NULL
            )
        """)
        conn.commit()


def authorized():
    if not WEBHOOK_API_KEY:
        return True
    supplied = request.headers.get("X-API-Key", "")
    return supplied == WEBHOOK_API_KEY


def save_payment(payload):
    trans_id = str(payload.get("TransID") or "").strip()
    if not trans_id:
        return False, "Missing TransID"

    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            try:
                conn.execute("""
                    INSERT INTO payments (
                        trans_id, transaction_type, trans_time, trans_amount,
                        business_short_code, bill_ref_number, invoice_number,
                        org_account_balance, third_party_trans_id, msisdn,
                        first_name, middle_name, last_name, raw_json, received_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trans_id,
                    payload.get("TransactionType"),
                    payload.get("TransTime"),
                    float(payload.get("TransAmount") or 0),
                    str(payload.get("BusinessShortCode") or ""),
                    payload.get("BillRefNumber"),
                    payload.get("InvoiceNumber"),
                    payload.get("OrgAccountBalance"),
                    payload.get("ThirdPartyTransID"),
                    payload.get("MSISDN"),
                    payload.get("FirstName"),
                    payload.get("MiddleName"),
                    payload.get("LastName"),
                    request.get_data(as_text=True),
                    datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
                return True, "saved"
            except sqlite3.IntegrityError:
                return True, "duplicate"


@app.get("/")
def home():
    return jsonify({
        "service": "M-Pesa C2B Webhook",
        "till": TILL_NUMBER,
        "status": "online"
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok", "till": TILL_NUMBER}), 200


@app.post("/webhook/validation")
def validation():
    # External validation is optional on Safaricom C2B.
    # If enabled for the Till, this endpoint accepts the payment.
    if not authorized():
        return jsonify({"ResultCode": "1", "ResultDesc": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    print("C2B VALIDATION:", payload, flush=True)

    return jsonify({
        "ResultCode": "0",
        "ResultDesc": "Accepted"
    }), 200


@app.post("/webhook/confirmation")
def confirmation():
    if not authorized():
        return jsonify({"ResultCode": "1", "ResultDesc": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    print("C2B CONFIRMATION:", payload, flush=True)

    # Guard against accidentally receiving a different short code.
    business_shortcode = str(payload.get("BusinessShortCode") or "")
    if business_shortcode and business_shortcode != TILL_NUMBER:
        return jsonify({
            "ResultCode": "1",
            "ResultDesc": "ShortCode does not match configured Till"
        }), 400

    ok, status = save_payment(payload)

    if not ok:
        return jsonify({"ResultCode": "1", "ResultDesc": status}), 400

    # Safaricom expects a successful HTTP response.
    return jsonify({
        "ResultCode": "0",
        "ResultDesc": "Accepted"
    }), 200


@app.get("/api/payments")
def payments():
    # The ERP can poll this endpoint every 15 seconds.
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        limit = min(max(int(request.args.get("limit", "50")), 1), 200)
    except ValueError:
        limit = 50

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, trans_id, transaction_type, trans_time, trans_amount,
                   business_short_code, bill_ref_number, invoice_number,
                   org_account_balance, third_party_trans_id, msisdn,
                   first_name, middle_name, last_name, received_at
            FROM payments
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return jsonify({
        "till": TILL_NUMBER,
        "count": len(rows),
        "payments": [dict(r) for r in rows]
    })


@app.get("/api/payments/latest")
def latest_payment():
    if not authorized():
        return jsonify({"error": "Unauthorized"}), 401

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT id, trans_id, transaction_type, trans_time, trans_amount,
                   business_short_code, bill_ref_number, invoice_number,
                   org_account_balance, third_party_trans_id, msisdn,
                   first_name, middle_name, last_name, received_at
            FROM payments
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

    return jsonify(dict(row) if row else {"payment": None})


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
else:
    init_db()
