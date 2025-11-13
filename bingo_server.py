# bingo_server.py
from flask import Flask, request, jsonify, send_file
from datetime import datetime
import psycopg2
from datetime import datetime
import pandas as pd
DB_URL = "postgresql://bingo_user:NGMW9BINy2WxDhFBU59LJtxcETdgdZOx@dpg-d4aktc24d50c73cmmefg-a/bingo_9ys8"



app = Flask(__name__)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            amount INTEGER,          
            tickets INTEGER,
            valid_until TEXT,
            outcome TEXT,
            message TEXT,
            timestamp TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()



def get_connection():
    return psycopg2.connect(DB_URL)
def insert_scan(code, amount, tickets=None, valid_until=None, outcome="accepted", message=""):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO scans (code, amount, tickets, valid_until, outcome, message, timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (code, amount, tickets, valid_until, outcome, message, datetime.utcnow())
        )
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()  # Si el código ya existe
    cur.close()
    conn.close()


@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "JSON requerido"}), 400

    
    qr_code = data.get("code", "")
    tickets = data.get("tickets", 0)
    valid_until = data.get("valid_until", "")
    amount = data.get("amount",0)

    if not qr_code:
        return jsonify({"ok": False, "message": "Falta el código QR"}), 400

 # Verificar duplicado f
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT amount, tickets, valid_until FROM scans WHERE code=%s", (qr_code,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        prev_amount, prev_tickets, prev_valid_until = row
        return jsonify({
            "ok": False,
            "message": "Este código QR ya fue escaneado",
            "amount": prev_amount,
            "tickets": prev_tickets,
            "valid_until": prev_valid_until
        }), 400

    insert_scan(qr_code, amount, tickets, valid_until, "accepted", f"tickets:{tickets}")
    cur.close()
    conn.close()
    return jsonify({"ok": True, "message": f"Código {qr_code} registrado", "tickets": tickets, "valid_until": valid_until})



@app.route("/admin/export", methods=["GET"])
def admin_export():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM scans", conn)
    conn.close()
    csv_path = "scans_export.csv"
    df.to_csv(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)

@app.route("/admin/scans", methods=["GET"])
def admin_scans():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM scans ORDER BY timestamp DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/admin/delete_all", methods=["POST"])
def delete_all_scans():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM scans")
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True, "message": "Todos los registros de scans han sido borrados"})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
