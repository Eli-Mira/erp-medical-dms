#!/bin/bash
set -e
echo "=== Installing erp-medical-dms ==="
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "Done. Run: python -m app"
