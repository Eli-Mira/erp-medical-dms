@echo off
echo === Installing erp-medical-dms ===
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
echo Done. Run: python -m app
