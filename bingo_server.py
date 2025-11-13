# bingo_server.py
from flask import Flask, request, jsonify, send_file, render_template
import sqlite3
import os
import json
import hmac
import hashlib
from datetime import datetime
import pandas as pd

DB_FILE = "bingo_scans.db"
SECRET_KEY = os.environ.get("BINGO_SECRET_KEY", "CAMBIA_ESTA_SECRETA_POR_PRODUCCION")

# Lista simple de autorizados (puedes cargar desde archivo/DB). En evento, da token o usar email.
AUTHORIZED = {
    "admin@example.com",
    # agrega los correos/dispositivos que pueden registrar escaneos
}
print("SECRET_KEY:", SECRET_KEY)

app = Flask(__name__)

def init_db():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS codes (
        code TEXT PRIMARY KEY,
        tickets INTEGER,
        valid_until TEXT,
        sig TEXT,
        initial_file TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        scanner TEXT,
        timestamp TEXT,
        outcome TEXT,
        message TEXT
    )
    """)
    con.commit()
    con.close()

def verify_signature(payload_dict, sig, secret):
    p = {k:v for k,v in payload_dict.items() if k != "sig"}
    p_json = json.dumps(p, separators=(",", ":"), sort_keys=True)
    expected = hmac.new(secret.encode(), p_json.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)

def get_code_record(code):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT code,tickets,valid_until,sig,initial_file FROM codes WHERE code=?", (code,))
    row = cur.fetchone()
    con.close()
    return row

def insert_scan(code, scanner, outcome, message=""):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("INSERT INTO scans(code,scanner,timestamp,outcome,message) VALUES (?,?,?, ?,?)",
                (code, scanner, datetime.utcnow().isoformat(), outcome, message))
    con.commit()
    con.close()

@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "JSON requerido"}), 400

    scanner = data.get("scanner", "")
    qr_payload_data = data.get("qr_payload", {})
    qr_code = qr_payload_data.get("code", "")
    tickets = qr_payload_data.get("tickets", 0)
    sig = qr_payload_data.get("sig", "")
    valid_until = qr_payload_data.get("valid_until", "")

    # Verificar campos mínimos
    if not qr_code or not sig:
        insert_scan(qr_code, scanner, "invalid", "missing fields")
        return jsonify({
            "ok": False,
            "status": "error",
            "message": "Faltan campos en el QR.",
            "tickets": None,
            "valid_until": None
        }), 400

    # Verificar firma
    if not verify_signature(qr_payload_data, sig, SECRET_KEY):
        insert_scan(qr_code, scanner, "invalid", "bad signature")
        return jsonify({
            "ok": False,
            "status": "error",
            "message": "Firma inválida. QR manipulado o no válido.",
            "tickets": None,
            "valid_until": None
        }), 400

    # Verificar expiración
    if valid_until:
        try:
            expire_date = datetime.fromisoformat(valid_until)
            if datetime.utcnow() > expire_date:
                insert_scan(qr_code, scanner, "expired", "code expired")
                return jsonify({
                    "ok": False,
                    "status": "warning",
                    "message": f"Este QR expiró el {valid_until}.",
                    "tickets": tickets,
                    "valid_until": valid_until
                }), 400
        except Exception:
            pass

    # Revisar duplicado
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM scans WHERE code=? AND outcome='accepted'", (qr_code,))
    accepted_count = cur.fetchone()[0]
    con.close()

    if accepted_count >= 1:
        insert_scan(qr_code, scanner, "duplicate", "ya se escaneó este código")
        return jsonify({
            "ok": False,
            "status": "warning",
            "message": "Este código QR ya fue escaneado anteriormente.",
            "tickets": tickets,
            "valid_until": valid_until
        }), 400

    # Registrar escaneo aceptado
    insert_scan(qr_code, scanner, "accepted", f"tickets:{tickets}")

    # Devuelve JSON final
    return jsonify({
        "ok": True,
        "status": "success" if scanner in AUTHORIZED else "warning",
        "message": f"Código: {qr_code}" if scanner in AUTHORIZED else "Escaneo no autorizado",
        "tickets": tickets,
        "valid_until": valid_until
    })

@app.route("/admin/export", methods=["GET"])
def admin_export():
    # Exporta todos los scans a CSV
    con = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM scans", con)
    con.close()
    csv_path = "scans_export.csv"
    df.to_csv(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)

@app.route("/admin/codes", methods=["GET"])
def admin_codes():
    con = sqlite3.connect(DB_FILE)
    df_codes = pd.read_sql_query("SELECT * FROM codes", con)
    df_scans = pd.read_sql_query("SELECT code, COUNT(*) as scans_total, SUM(CASE WHEN outcome='accepted' THEN 1 ELSE 0 END) as accepted_count FROM scans GROUP BY code", con)
    con.close()
    merged = pd.merge(df_codes, df_scans, how="left", left_on="code", right_on="code")
    merged.fillna({"scans_total":0, "accepted_count":0}, inplace=True)
    return merged.to_json(orient="records")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
