# PostgreSQL Migration & Setup Guide

## Overview
This project now uses PostgreSQL exclusively for application state, audit history, file metadata, AI logs, costing data, and generated document tracking. The backend runtime path is PostgreSQL-only.

## Local PostgreSQL Setup

### 1. Install PostgreSQL
- Windows: use the PostgreSQL installer or Chocolatey.
- macOS: `brew install postgresql@16`
- Ubuntu/Debian: `sudo apt install postgresql postgresql-contrib`

### 2. Create database and user
```sql
CREATE DATABASE cost_estimator;
CREATE USER estimator_user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE cost_estimator TO estimator_user;
```

### 3. Configure environment
Set in `backend/.env`:
```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/cost_estimator
```

### 4. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 5. Run migrations
```bash
alembic upgrade head
```

### 6. Start the backend
```bash
uvicorn app.main:app --reload
```

## Migration Commands
- Create a new migration shell:
```bash
alembic revision --autogenerate -m "describe change"
```
- Apply migrations:
```bash
alembic upgrade head
```
- Roll back last migration:
```bash
alembic downgrade -1
```

## Database Health Checks
- `GET /health` returns service health.
- `GET /health/db` checks PostgreSQL connectivity and pool status.

Example response:
```json
{
  "database": "connected",
  "status": "healthy",
  "driver": "asyncpg",
  "pool_status": "Pool size: ..."
}
```

## Schema Summary
### Core operational tables
- `jobs`
- `uploaded_files`
- `extracted_data`
- `costing_sheets`
- `quotations`
- `cover_letters`
- `rate_configurations`
- `chat_history`
- `audit_logs`

### Enterprise foundation tables
- `companies`
- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`
- `refresh_tokens`
- `login_history`
- `system_settings`
- `user_settings`
- `ai_processing_logs`

## File Metadata Tracking
Every uploaded or generated file should create a row in `uploaded_files` with:
- original filename
- stored filename
- file type
- file origin (`upload` or `generated`)
- checksum SHA-256
- storage provider
- blob reference or path
- processing status
- timestamps
- upload/output size

Actual file bytes may remain in local storage or Azure Blob Storage, but metadata is always persisted in PostgreSQL.

## ER Diagram Summary
- `companies` own many `jobs`.
- `jobs` own uploaded files, extracted data, quotations, costing sheets, cover letters, chat history, and audit logs.
- `users` belong to a company and can hold multiple roles.
- `roles` and `permissions` are linked via junction tables.
- `refresh_tokens` and `login_history` support authentication auditing.
- `ai_processing_logs` tracks prompt/response metadata for extraction and drafting workflows.

## Security Notes
- Keep passwords hashed only.
- Store refresh token hashes, not raw tokens.
- Use parameterized ORM queries only.
- Keep PostgreSQL credentials out of source control.
- Use SSL/TLS for Azure PostgreSQL connections in production.

## Performance Notes
- Use PostgreSQL indexes on job status, reference numbers, timestamps, and file checksums.
- Prefer JSONB for AI payloads and extracted document snapshots.
- Use connection pooling with `pool_pre_ping=True`.
- Page list endpoints with `limit` and `offset`.

## Backup Strategy
- Nightly logical backups with `pg_dump`.
- Retain point-in-time recovery for production.
- Back up Azure Blob files separately from the database.
- Test restore procedures regularly.

## Rollback Strategy
- Roll back code with Git if schema is unchanged.
- Use `alembic downgrade -1` or `alembic downgrade <revision>` for database rollback.
- Keep pre-migration backups before applying production migrations.

## Migration Risks
- Existing legacy database data must be exported and transformed before the first PostgreSQL cutover.
- JSON/text columns may need normalization during data import.
- UUID and timestamp types may require casting during one-time migration scripts.
- Generated document rows may need a backfill if historical files should be tracked.

## PostgreSQL Optimization Suggestions
- Add GIN indexes for JSONB fields used in search.
- Add composite indexes on `(job_id, created_at)` for history tables.
- Consider partitioning very large audit/log tables later.
- Use read-only replicas for reporting if load grows.

## Future Scaling Recommendations
- Move AI processing logs and activity streams into partitioned tables if growth is heavy.
- Add dedicated document archive retention policies.
- Split read-heavy analytics into reporting views or replicas.
- Externalize blobs to Azure Blob Storage and keep only metadata in PostgreSQL.

## Testing Checklist
1. Migration testing
2. API smoke testing
3. Authentication testing
4. File upload testing
5. Costing sheet generation testing
6. RFQ workflow testing
7. Rollback testing
8. Load testing

## Startup Commands
```bash
alembic upgrade head
uvicorn app.main:app --reload
```

## Verification Commands
```sql
SELECT 1;
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
```

## Production Deployment Notes
- Use Azure Database for PostgreSQL Flexible Server.
- Enable SSL required connections.
- Set `DATABASE_URL` through Azure App Service configuration.
- Run migrations during deployment before app startup or via release task.
- Keep storage paths or Azure Blob containers configured separately from Postgres.
