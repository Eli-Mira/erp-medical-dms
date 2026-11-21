# Third-Party Notices — ElsebaeyPharma ERP

Per Eli Phase 0 Decision `T11` (`source=eli-typed`, `2026-11-21`), Eli retains reusable ERP core IP and grants ElsebaeyPharma a perpetual, non-exclusive internal-use license. Third-party open-source dependencies retain their respective permissive licenses below. ERPNext (GPL-3.0) was consulted for high-level conceptual architecture ONLY; zero GPL-3.0 code or text is included.

| Package | Version | License | Scope | Source |
|---|---|---|---|---|
| FastAPI | 0.136.1 | MIT | Core API (`requirements.txt`) | https://github.com/fastapi/fastapi |
| Uvicorn | 0.44.0 | BSD-3-Clause | ASGI Server (`requirements.txt`) | https://github.com/encode/uvicorn |
| SQLAlchemy | 2.0.x | MIT | DB / SQL Core (`requirements.txt`) | https://github.com/sqlalchemy/sqlalchemy |
| Alembic | 1.20.1 | MIT | Migrations (`requirements.txt`) | https://github.com/sqlalchemy/alembic |
| psycopg | 3.x | LGPL-3.0 (dynamically linked Python package) | PostgreSQL Driver (`requirements.txt`) | https://github.com/psycopg/psycopg |
| Pydantic | 2.x | MIT | Validation (`requirements.txt`) | https://github.com/pydantic/pydantic |
| httpx | 0.28.x | BSD-3-Clause | HTTP Client (`requirements.txt`) | https://github.com/encode/httpx |
| openpyxl | 3.1.x | MIT | Excel Workbook Reader (`requirements.txt`) | https://openpyxl.readthedocs.io/ |
| **aiogram** | **3.33.0** | **MIT** | **Optional Telegram Bot (`requirements-telegram.txt`, Eli `T3`)** | https://github.com/aiogram/aiogram |
