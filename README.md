# Medical Company System (ERP)

Egyptian medical-distribution ERP-lite. FastAPI + PostgreSQL + vanilla JS PWA.

## Database URL

The database connection URL must be supplied via the `DATABASE_URL` environment
variable. No credentials are stored in this repository. Example:

```
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/DBNAME
```

`alembic.ini` and `app/db.py` contain placeholder values only. Set `DATABASE_URL`
before running migrations or the application.