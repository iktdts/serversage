# Running Migrations with Docker

## Overview

Since your database runs in Docker on the `dbnet` network, the migration scripts also need to run in Docker to access the database.

## Quick Start

### One Command:
```bash
./migrations/run_migrations.sh
```

This interactive script will:
1. Check prerequisites (networks, secrets)
2. Let you choose which migration to run
3. Build and run the migration container
4. Show progress and results

---

## Manual Commands

### Migration 1: Verified Users Roles (Automated)

```bash
# Build the migration container
docker compose -f migrations/docker-compose.yml build migrate_verified_users

# Run the migration
docker compose -f migrations/docker-compose.yml run --rm migrate_verified_users
```

**Output:** Automated migration with progress per user and final summary.

---

### Migration 2: Unmapped Skills (Interactive)

```bash
# Build the migration container
docker compose -f migrations/docker-compose.yml build migrate_unmapped_skills

# Run the interactive migration
docker compose -f migrations/docker-compose.yml run --rm migrate_unmapped_skills
```

**Output:** Interactive - you'll validate each batch of extracted skills.

---

## Prerequisites

### 1. Docker Networks

Ensure these networks exist:
```bash
docker network create dbnet
docker network create bot
```

Or check if they exist:
```bash
docker network ls | grep -E 'dbnet|bot'
```

### 2. Secrets Files

Create secret files if they don't exist:
```bash
# Discord token
echo 'your_discord_bot_token' > ./secrets/discord_token.txt

# Database password
echo 'your_database_password' > ./secrets/db_password.txt
```

### 3. Postgres Container

Ensure your PostgreSQL container is running:
```bash
docker ps | grep postgres
```

If not running:
```bash
docker compose up -d postgres
```

---

## How It Works

### Container Configuration

The migration containers:
- Use `Dockerfile.migrations` (Python 3.11 + dependencies)
- Connect to `dbnet` network (to access postgres)
- Connect to `bot` network (to access Discord)
- Mount secrets for credentials
- Use same `.env` as main bot

### Network Access

```
Migration Container
       ↓
    dbnet network
       ↓
  postgres container (DATABASE_HOST=postgres)
```

### Environment Variables

From `.env` and docker-compose:
```bash
DATABASE_HOST=postgres        # Points to postgres container
DATABASE_PORT=5432
DATABASE_NAME=discord
DATABASE_USER=discord
DATABASE_PASSWORD_FILE=/run/secrets/db_password
DISCORD_BOT_TOKEN_FILE=/run/secrets/discord_bot_token
```

---

## Troubleshooting

### "Network not found"

**Error:**
```
ERROR: Network dbnet declared as external, but could not be found
```

**Fix:**
```bash
docker network create dbnet
docker network create bot
```

---

### "Cannot connect to database"

**Error:**
```
could not connect to server: Connection refused
```

**Fix:**
1. Check postgres container is running:
   ```bash
   docker ps | grep postgres
   ```

2. Start postgres if needed:
   ```bash
   docker compose up -d postgres
   ```

3. Verify network connection:
   ```bash
   docker compose -f docker-compose.migrations.yml run --rm migrate_verified_users \
     bash -c "apt-get update && apt-get install -y postgresql-client && \
     PGPASSWORD=\$(cat /run/secrets/db_password) psql -h postgres -U discord -d discord -c 'SELECT 1;'"
   ```

---

### "Secret file not found"

**Error:**
```
❌ ./secrets/discord_token.txt not found
```

**Fix:**
```bash
mkdir -p secrets
echo 'your_discord_bot_token' > ./secrets/discord_token.txt
echo 'your_database_password' > ./secrets/db_password.txt
```

---

### Interactive migration not working

**Issue:** Can't interact with the migration script

**Fix:** Ensure you're using `docker compose run` (not `up`):
```bash
docker compose -f migrations/docker-compose.yml run --rm migrate_unmapped_skills
```

The `run` command with `stdin_open: true` and `tty: true` enables interactive input.

---

## Advanced Usage

### Run migrations with different database

Override environment variables:
```bash
docker compose -f migrations/docker-compose.yml run --rm \
  -e DATABASE_HOST=other-postgres \
  -e DATABASE_NAME=other_db \
  migrate_verified_users
```

### View logs

Since migrations run once and exit, logs appear in real-time. To save logs:
```bash
docker compose -f migrations/docker-compose.yml run --rm migrate_verified_users 2>&1 | tee migration.log
```

### Test database connection

```bash
docker compose -f migrations/docker-compose.yml run --rm migrate_verified_users \
  python -c "from config import settings; print(f'DB URL: {settings.DATABASE_URL}')"
```

---

## Files Created

- **`migrations/Dockerfile`** - Dockerfile for migration containers
- **`migrations/docker-compose.yml`** - Docker Compose configuration
- **`migrations/run_migrations.sh`** - Interactive helper script

---

## After Migration

Once migrations complete:

1. **Start the bot:**
   ```bash
   docker compose up -d
   ```

2. **Verify data:**
   ```bash
   docker compose exec postgres psql -U discord -d discord
   ```
   
   ```sql
   -- Check migrated roles
   SELECT COUNT(*) FROM assigned_roles;
   
   -- Check unmapped skills
   SELECT COUNT(*) FROM unmapped_skills;
   
   -- View sample data
   SELECT * FROM assigned_roles LIMIT 5;
   ```

3. **Monitor bot logs:**
   ```bash
   docker compose logs -f serversage
   ```

---

## Summary

**Easiest method:**
```bash
./migrations/run_migrations.sh
```

**Manual method:**
```bash
# Build
docker compose -f migrations/docker-compose.yml build

# Run verified users migration
docker compose -f migrations/docker-compose.yml run --rm migrate_verified_users

# Run unmapped skills migration (interactive)
docker compose -f migrations/docker-compose.yml run --rm migrate_unmapped_skills
```

**Cleanup:**
```bash
# Remove migration images after use (optional)
docker compose -f migrations/docker-compose.yml down --rmi all
```

---

**Need help?** Check the main documentation in `docs/DATABASE_SETUP.md`
