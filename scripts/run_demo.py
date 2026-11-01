import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = os.environ["DATABASE_URL"]  # Require an explicit target.
os.environ["POSTING_ENABLED"] = "false"
os.environ["DEMO_MODE"] = "1"
import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8018)
