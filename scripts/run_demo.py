import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "postgresql+psycopg://dms:dms-dev@localhost:5432/medical_demo"
os.environ["POSTING_ENABLED"] = "false"
os.environ["DEMO_MODE"] = "1"
import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8018)
