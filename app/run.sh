#!/usr/bin/env bash
# CHELLO DWAR - one-command launcher (Linux/macOS)
cd "$(dirname "$0")"
command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }
python3 -m pip install -q -r requirements.txt 2>/dev/null || pip3 install -q -r requirements.txt
echo "CHELLO DWAR running on https://localhost:8443 (accept the self-signed cert once)"
python3 -m uvicorn app:app --host 0.0.0.0 --port 8443 --ssl-certfile cert.pem --ssl-keyfile cert_key.pem
