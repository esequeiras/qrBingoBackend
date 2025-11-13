# generate_qrs.py
import base64
import os
from shlex import quote
import uuid
import json
import hmac
import hashlib
from datetime import datetime
import qrcode
import pandas as pd

# --- CONFIG ---
OUTPUT_DIR = "qrcodes"
CSV_FILENAME = "codes.csv"
XLSX_FILENAME = "codes.xlsx"
SECRET_KEY = os.environ.get("BINGO_SECRET_KEY", "CAMBIA_ESTA_SECRETA_POR_PRODUCCION")
# Ejemplo: SECRET_KEY = "mi_super_secreto"
# ----------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

def sign_payload(payload_dict, secret):
    """
    Crea HMAC-SHA256 sobre el JSON minificado del payload.
    """
    payload_json = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
    return sig

def make_qr_image(data_str, out_path):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(out_path)

def generate_codes(num_codes=100, tickets_options=[1], valid_until=None, label_prefix="BINGO"):
    """
    tickets_options: puede ser lista; si >1 se elige aleatoriamente o puedes pasar una lista con la cantidad para cada código.
    valid_until: string ISO 'YYYY-MM-DD' o None
    """
    import random
    rows = []
    for i in range(num_codes):
        code = str(uuid.uuid4())
        tickets = random.choice(tickets_options) if isinstance(tickets_options, (list,tuple)) else tickets_options
        payload = {
            "code": code,
            "tickets": int(tickets),
            "valid_until": valid_until or ""
        }
        sig = sign_payload(payload, SECRET_KEY)
        payload["sig"] = sig
        filename = f"{label_prefix}_{i+1}_{code[:8]}.png"
        out_path = os.path.join(OUTPUT_DIR, filename)

        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
        url = f"https://esequeiras.github.io/QrsBingo/?data={quote(payload_b64)}"


        make_qr_image(url, out_path)
        rows.append({
            "code": code,
            "tickets": tickets,
            "valid_until": valid_until or "",
            "sig": sig,
            "file": out_path
        })
    df = pd.DataFrame(rows)
    df.to_csv(CSV_FILENAME, index=False)
    df.to_excel(XLSX_FILENAME, index=False)
    print(f"Generados {len(rows)} QRs en {OUTPUT_DIR}. CSV: {CSV_FILENAME} XLSX: {XLSX_FILENAME}")
    return df

if __name__ == "__main__":
    # Ejemplo: 50 códigos; algunos por 1 cartón y algunos por 5 cartones; válido hasta el día del bingo.
    df = generate_codes(num_codes=20, tickets_options=[1,5], valid_until="2025-11-30", label_prefix="BINGO")
