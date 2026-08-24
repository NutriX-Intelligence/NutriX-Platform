# Database Setup & Migration Reference

This directory contains database seeding scripts to populate the PostgreSQL database. This guide details standard scenarios for re-initializing a wiped database or migrating data to a cloud database environment.

---

## Scenario 1: Re-initializing and Seeding (After Volume Wipe)
If you executed `docker-compose down -v` (which deletes the persistent Docker volume), follow these steps to rebuild the database schema and re-run all seeders.

### Steps
1. **Start fresh containers** (this creates a new empty volume):
   ```bash
   docker-compose up -d postgres redis
   ```
2. **Activate the virtual environment**:
   ```bash
   source .venv/bin/activate
   ```
3. **Export connection environment variable** (pointing to your local container):
   ```bash
   export DATABASE_URL=postgresql://nutrix:nutties@localhost:5432/nutrix_db
   ```
4. **Run database migrations** (creates the 34 tables and live triggers):
   ```bash
   PYTHONPATH=. alembic upgrade head
   ```
5. **Ingest the datasets**:
   ```bash
   PYTHONPATH=. python shared/seeders/run_all_seeders.py
   ```

---

## Scenario 2: Migrating to a Cloud Database
If you are moving from local development to a cloud-hosted PostgreSQL instance (e.g., AWS RDS, Supabase, Neon), choose one of the following two options:

### Option A: Schema Migration & Seeder Execution (Easiest)
This option creates a clean database schema and seeds it from source files over the internet.

1. **Activate the virtual environment**:
   ```bash
   source .venv/bin/activate
   ```
2. **Export your cloud connection URL**:
   ```bash
   export DATABASE_URL="postgresql://<username>:<password>@<cloud-host>:<port>/<dbname>"
   ```
3. **Apply the migrations** (creates all tables and trigger logic in the cloud):
   ```bash
   PYTHONPATH=. alembic upgrade head
   ```
4. **Upload the data** using the seeding pipeline:
   ```bash
   PYTHONPATH=. python shared/seeders/run_all_seeders.py
   ```

### Option B: Database Dump & Restore (Fastest for Large Datasets)
Instead of row-by-row uploads, this option exports your fully-seeded local database as a compressed SQL snapshot and restores it directly to the cloud.

1. **Create a local database dump** (runs while the local postgres container is active):
   ```bash
   docker exec -t nutrix-postgres pg_dumpall -c -U nutrix > backup.sql
   ```
2. **Restore the backup directly to the cloud**:
   ```bash
   psql -h <cloud-host> -p <port> -U <cloud-username> -d <cloud-dbname> -f backup.sql
   ```
   *(Note: Ensure your cloud PostgreSQL user has permission to create tables and triggers).*
