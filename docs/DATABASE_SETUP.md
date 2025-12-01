# Database Setup and Migration Guide

## Overview

ServerSage now includes PostgreSQL database integration to track user role assignments, role history, and unmapped skills. This guide covers setup, configuration, and migration of existing data.

## Database Schema

### Tables

1. **`roles`** - Stores Discord role metadata
   - `role_id` (PRIMARY KEY): Discord role ID
   - `role_name`: Role name
   - `category`: Role category (e.g., "Programming_Language", "Experience_Level")
   - `created_at`, `updated_at`: Timestamps

2. **`assigned_roles`** - Current role assignments for users
   - `id` (PRIMARY KEY): Auto-increment ID
   - `user_id`: Discord user ID
   - `role_id` (FOREIGN KEY -> roles.role_id): Assigned role
   - `assigned_at`: When the role was assigned
   - `assigned_by`: Source ("verification", "manual_assignment", "discord_event")
   - **Note**: Foreign key with CASCADE DELETE - when a role is deleted, all assignments are automatically removed

3. **`role_history`** - Historical record of role changes
   - `id` (PRIMARY KEY): Auto-increment ID
   - `user_id`: Discord user ID
   - `role_name`: Role name at the time of the operation
   - `action`: "added" or "removed"
   - `triggered_by`: What caused the change
   - `timestamp`: When the change occurred

4. **`unmapped_skills`** - Skills mentioned by users without matching roles
   - `id` (PRIMARY KEY): Auto-increment ID
   - `user_id`: Discord user ID
   - `user_name`: Discord username
   - `skill_name`: The skill mentioned
   - `suggested_category`: LLM-suggested category
   - `mentioned_at`: Timestamp
   - `source`: "verification" or "migration"

## Setup

### 1. PostgreSQL Installation

Install PostgreSQL:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# macOS (using Homebrew)
brew install postgresql@15
brew services start postgresql@15

# Verify installation
psql --version
```

### 2. Create Database and User

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE serversage;
CREATE USER serversage WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE serversage TO serversage;

# Exit psql
\q
```

### 3. Configure Environment Variables

Update your `.env` file:

```bash
# Database Configuration
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=serversage
DATABASE_USER=serversage
DATABASE_PASSWORD=your_secure_password

# For Docker secrets (alternative to DATABASE_PASSWORD)
# DATABASE_PASSWORD_FILE=/run/secrets/db_password

# Channel for historical unmapped skills scanning
UNMAPPED_SKILLS_CHANNEL_ID=1425165578825371799
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

The following packages will be installed:
- `asyncpg~=0.29.0` - PostgreSQL async driver
- `SQLAlchemy[asyncio]~=2.0.30` - ORM with async support
- `alembic~=1.13.1` - Database migrations

### 5. Test Database Connection

The bot will automatically create tables on startup. Run the bot to verify:

```bash
python main.py
```

Check logs for:
```
INFO - Database initialized successfully.
INFO - DatabaseService initialized.
```

## Docker Setup with Secrets

For production deployments using Docker, use secrets for the database password:

### 1. Create Docker Secret

```bash
echo "your_secure_password" | docker secret create db_password -
```

### 2. Update `docker-compose.yml`

```yaml
version: '3.8'

services:
  bot:
    build: .
    secrets:
      - db_password
      - discord_token
      - llm_api_token
    environment:
      DATABASE_HOST: postgres
      DATABASE_PORT: 5432
      DATABASE_NAME: serversage
      DATABASE_USER: serversage
      DATABASE_PASSWORD_FILE: /run/secrets/db_password
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: serversage
      POSTGRES_USER: serversage
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

secrets:
  db_password:
    external: true
  discord_token:
    external: true
  llm_api_token:
    external: true

volumes:
  postgres_data:
```

## Data Migration

After setting up the database, you need to migrate existing data.

### Migration 1: Verified Users' Roles

This migration captures current role assignments for all verified members.

```bash
python scripts/migrate_verified_users_roles.py
```

**What it does:**
1. Connects to Discord
2. Loads `data/categorized_roles.json`
3. Syncs all categorized roles to the `roles` table
4. Finds all members with the VERIFIED_ROLE_ID
5. Captures their current managed roles
6. Stores assignments in `assigned_roles` table with history

**Output:**
```
Migration Summary:
  Total verified members: 245
  Successfully migrated: 198
  Skipped (no roles or bots): 47
```

### Migration 2: Historical Unmapped Skills

This migration scans channel history for "Unmappable Skill Alert" messages and extracts skill data.

```bash
python scripts/migrate_unmapped_skills.py
```

**Features:**
- **Interactive**: Processes messages in batches (default: 100)
- **Validation**: Shows extracted data before saving
- **Resumable**: Can quit and resume later
- **Rate-limit safe**: Batched processing prevents API rate limits

**Example workflow:**
```
Batch 1: Fetching next 100 messages...
==================================================================

  Found 3 unmappable skill alert(s) in this batch:
  ======================================================================

  1. User: julissazorra (ID: 123456789)
     Skill: Next.js
     Category: Framework
     Mentioned: 2025-01-15 14:23:45 UTC

  2. User: goldcoin222 (ID: 987654321)
     Skill: node.js
     Category: Tool
     Mentioned: 2025-01-14 09:12:33 UTC

  ======================================================================

  Do you want to save these skills to the database? (yes/no/quit): yes
  ✓ Saved 3 skills to database.

  Continue to next batch? (yes/no): yes
```

**Commands during migration:**
- `yes` / `y` - Save current batch and continue
- `no` / `n` - Skip current batch without saving
- `quit` / `q` - Stop migration

## Ongoing Database Maintenance

After migration, the database is automatically maintained:

### Automatic Role Sync

The `RoleSyncCog` listens to Discord events:

1. **`on_guild_role_create`** - New roles are added to `roles` table
2. **`on_guild_role_delete`** - Deleted roles cascade delete from `assigned_roles`
3. **`on_guild_role_update`** - Role renames update the `roles` table
4. **`on_member_update`** - Role changes (add/remove) update `assigned_roles` and `role_history`

### Automatic Verification Tracking

When users complete verification:
- Assigned roles → `assigned_roles` table
- Unmapped skills → `unmapped_skills` table
- All changes → `role_history` table

### Manual Role Updates

When users use `/assign-roles`:
- Previous roles → `role_history` (marked "removed")
- New roles → `assigned_roles` + `role_history` (marked "added")
- Source: `manual_assignment`

## Database Queries (for Admins)

### Check User's Current Roles

```sql
SELECT r.role_name, ar.assigned_at, ar.assigned_by
FROM assigned_roles ar
JOIN roles r ON ar.role_id = r.role_id
WHERE ar.user_id = 123456789
ORDER BY ar.assigned_at DESC;
```

### View User's Role History

```sql
SELECT role_name, action, triggered_by, timestamp
FROM role_history
WHERE user_id = 123456789
ORDER BY timestamp DESC
LIMIT 20;
```

### Find All Unmapped Skills

```sql
SELECT user_name, skill_name, suggested_category, mentioned_at
FROM unmapped_skills
ORDER BY mentioned_at DESC;
```

### Get Most Requested Unmapped Skills

```sql
SELECT skill_name, suggested_category, COUNT(*) as mentions
FROM unmapped_skills
GROUP BY skill_name, suggested_category
ORDER BY mentions DESC
LIMIT 10;
```

## Troubleshooting

### Database Connection Errors

**Error**: `FATAL: password authentication failed`

**Solution**: Check credentials in `.env` or Docker secrets

```bash
# Test connection manually
psql -h localhost -U serversage -d serversage
```

### Tables Not Created

**Error**: `relation "roles" does not exist`

**Solution**: Ensure bot has permission to create tables

```sql
-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO serversage;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO serversage;
```

### Migration Script Hangs

**Issue**: Script stops responding during message scanning

**Solution**: 
1. Check Discord API rate limits
2. Reduce batch size in script (change `BATCH_SIZE = 100` to `BATCH_SIZE = 50`)
3. Ensure bot has proper channel permissions

### Foreign Key Violations

**Error**: `violates foreign key constraint`

**Solution**: Sync roles to database before assigning them

```python
# Ensure role exists in database first
await db_service.sync_role(role_id=role.id, role_name=role.name, category=category)
# Then assign to user
await db_service.assign_roles_to_user(user_id=user_id, role_ids=[role.id])
```

## Backup and Recovery

### Backup Database

```bash
# Full database backup
pg_dump -U serversage -h localhost serversage > serversage_backup.sql

# Backup with timestamp
pg_dump -U serversage serversage > "serversage_$(date +%Y%m%d_%H%M%S).sql"
```

### Restore Database

```bash
# Restore from backup
psql -U serversage -h localhost serversage < serversage_backup.sql
```

### Automated Backups (cron)

```bash
# Add to crontab (daily backup at 2 AM)
0 2 * * * pg_dump -U serversage serversage > /backups/serversage_$(date +\%Y\%m\%d).sql
```

## Performance Optimization

### Indexes

The schema includes indexes on frequently queried columns:
- `assigned_roles`: `user_id`, `role_id`, `(user_id, role_id)`
- `role_history`: `user_id`, `timestamp`
- `unmapped_skills`: `user_id`, `skill_name`, `mentioned_at`

### Connection Pooling

The bot uses SQLAlchemy's connection pooling:
- Pool size: 10 connections
- Max overflow: 20 connections
- Connection recycling: 1 hour

### Vacuum and Analyze

Regular maintenance:

```sql
-- Analyze tables for query optimization
ANALYZE roles;
ANALYZE assigned_roles;
ANALYZE role_history;
ANALYZE unmapped_skills;

-- Vacuum to reclaim storage
VACUUM ANALYZE;
```

## Future Enhancements

Potential features to add:
- Alembic migrations for schema changes
- Analytics dashboard queries
- Role recommendation based on history
- Skill trend analysis
- User engagement metrics

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review error messages in console
3. Verify environment variables
4. Test database connection manually
5. Check Discord bot permissions

---

**Last Updated**: 2025-11-03
