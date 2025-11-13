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
BASE_OUTPUT_DIR = "qrcodes"
# ----------------



def make_qr_image(data_str, out_path):
    """Genera y guarda una imagen QR."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data_str)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(out_path)

def generate_codes(num_codes, tickets, amount, valid_until=None, label_prefix="BINGO", folder_name="qrcodes"):
    """
    Genera códigos QR y los guarda en carpeta, CSV y Excel separados.
    """
    output_dir = os.path.join(BASE_OUTPUT_DIR, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    rows = []
    for i in range(num_codes):
        code = str(uuid.uuid4())
        payload = {
            "code": code,
            "tickets": int(tickets),
            "valid_until": valid_until or "",
            "amount": amount

        }
        filename = f"{label_prefix}_{tickets}cartones_{i+1}_{code[:8]}.png"
        out_path = os.path.join(output_dir, filename)

        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
        url = f"https://esequeiras.github.io/QrsBingo/?data={quote(payload_b64)}"

        make_qr_image(url, out_path)
        rows.append({
            "code": code,
            "tickets": tickets,
            "valid_until": valid_until or "",
            "file": out_path
        })

    df = pd.DataFrame(rows)
    csv_path = os.path.join(output_dir, f"codes_{tickets}cartones.csv")
    xlsx_path = os.path.join(output_dir, f"codes_{tickets}cartones.xlsx")
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)
    print(f"✅ Generados {len(rows)} QRs con {tickets} cartones en {output_dir}")
    print(f"📄 Archivos: {csv_path} y {xlsx_path}")
    return df

if __name__ == "__main__":
    # Generar 250 QR con 5 cartones
    generate_codes(
        num_codes=250,
        tickets=5,
        amount=5000,
        valid_until="2025-11-30",
        label_prefix="BINGO",
        folder_name="qrcodes_5"
    )

    # Generar 200 QR con 1 cartón
    generate_codes(
        num_codes=200,
        tickets=1,
        amount=1000,
        valid_until="2025-11-30",
        label_prefix="BINGO",
        folder_name="qrcodes_1"
    )
