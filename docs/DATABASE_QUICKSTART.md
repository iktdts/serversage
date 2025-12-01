# Database Integration - Quick Start Checklist

## Prerequisites
- [ ] PostgreSQL installed
- [ ] Python 3.8+ installed
- [ ] Bot is already running and has generated `data/categorized_roles.json`

## Step 1: Database Setup (5 minutes)

### Option A: Automated Setup (Recommended)
```bash
./scripts/setup_database.sh
```
This will:
- Create PostgreSQL database and user
- Update `.env` file with credentials
- Test the connection

### Option B: Manual Setup
```bash
# Create database
sudo -u postgres psql
CREATE DATABASE serversage;
CREATE USER serversage WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE serversage TO serversage;
\q

# Update .env
echo "DATABASE_HOST=localhost" >> .env
echo "DATABASE_PORT=5432" >> .env
echo "DATABASE_NAME=serversage" >> .env
echo "DATABASE_USER=serversage" >> .env
echo "DATABASE_PASSWORD=your_password" >> .env
echo "UNMAPPED_SKILLS_CHANNEL_ID=your_channel_id" >> .env
```

## Step 2: Install Dependencies (2 minutes)
```bash
pip install -r requirements.txt
```

New packages:
- asyncpg
- SQLAlchemy[asyncio]
- alembic

## Step 3: Test Database Connection (1 minute)
```bash
python main.py
```

Look for in logs:
```
✓ Database initialized successfully.
✓ DatabaseService initialized.
✓ RoleSyncCog loaded successfully.
```

Stop the bot after verification (Ctrl+C).

## Step 4: Migration 1 - Verified Users Roles (5-10 minutes)

```bash
python scripts/migrate_verified_users_roles.py
```

**Expected output:**
```
Synced 45 roles to database.
Found 198 verified members.
✓ Migrated 5 roles for user_name (ID: 123456)
...
Migration Summary:
  Successfully migrated: 198
```

**Verification:**
```bash
sudo -u postgres psql serversage -c "SELECT COUNT(*) FROM assigned_roles;"
```

## Step 5: Migration 2 - Unmapped Skills (15-30 minutes)

This is **interactive** - you validate each batch before saving.

```bash
python scripts/migrate_unmapped_skills.py
```

**Process:**
1. Script fetches 100 messages
2. Shows extracted skills
3. You review and type `yes` to save or `no` to skip
4. You type `yes` to continue to next batch or `no` to stop

**Example session:**
```
Batch 1: Fetching next 100 messages...

  Found 3 unmappable skill alert(s):
  
  1. User: john_doe (ID: 123456)
     Skill: Next.js
     Category: Framework

  Do you want to save these skills? (yes/no/quit): yes
  ✓ Saved 3 skills to database.

  Continue to next batch? (yes/no): yes
```

**Tips:**
- Type `quit` anytime to stop (progress is saved)
- Can resume later - it will continue from where you left off
- Batches are processed oldest to newest

**Verification:**
```bash
sudo -u postgres psql serversage -c "SELECT COUNT(*) FROM unmapped_skills;"
```

## Step 6: Restart Bot (1 minute)

```bash
python main.py
```

The bot is now fully integrated with the database!

## Verification Tests

### Test 1: New User Verification
1. Have a test user run `/assign-roles`
2. Complete verification
3. Check database:
```sql
SELECT * FROM assigned_roles WHERE user_id = <test_user_id>;
SELECT * FROM role_history WHERE user_id = <test_user_id>;
```

### Test 2: Role Update
1. Test user runs `/assign-roles` again
2. Changes roles
3. Check history shows old roles removed, new ones added:
```sql
SELECT role_name, action, triggered_by, timestamp 
FROM role_history 
WHERE user_id = <test_user_id> 
ORDER BY timestamp DESC 
LIMIT 10;
```

### Test 3: Unmapped Skill
1. User mentions a non-existent skill during verification
2. Check database:
```sql
SELECT * FROM unmapped_skills WHERE user_id = <test_user_id>;
```

### Test 4: Discord Role Changes
1. Create a new role in Discord
2. Add it to a category in `categorized_roles.json`
3. Check database:
```sql
SELECT * FROM roles WHERE role_name = 'NewRole';
```

### Test 5: Role Deletion Cascade
1. Delete a role from Discord
2. Check database - assignments should be gone:
```sql
-- This should return 0 rows
SELECT * FROM assigned_roles WHERE role_id = <deleted_role_id>;
```

## Common Issues

### "Database connection failed"
- **Check**: PostgreSQL is running: `sudo systemctl status postgresql`
- **Check**: Credentials in `.env` are correct
- **Fix**: Test manually: `psql -h localhost -U serversage -d serversage`

### "Import discord could not be resolved"
- **Ignore**: These are just VS Code warnings if packages aren't installed in the environment
- **Test**: Run `python main.py` - if it starts, imports are fine

### Migration hangs
- **Check**: Bot has permission to read the channel
- **Fix**: Reduce batch size in script (change `BATCH_SIZE = 100` to `50`)

### "Role not found in guild"
- **Cause**: Role was deleted from Discord but exists in `categorized_roles.json`
- **Fix**: Normal - script will skip and log a warning

## Quick Database Queries

### See all users with roles
```sql
SELECT ar.user_id, r.role_name, ar.assigned_by, ar.assigned_at
FROM assigned_roles ar
JOIN roles r ON ar.role_id = r.role_id
ORDER BY ar.assigned_at DESC
LIMIT 20;
```

### Top unmapped skills
```sql
SELECT skill_name, COUNT(*) as mentions
FROM unmapped_skills
GROUP BY skill_name
ORDER BY mentions DESC
LIMIT 10;
```

### User's role timeline
```sql
SELECT role_name, action, triggered_by, timestamp
FROM role_history
WHERE user_id = 123456789
ORDER BY timestamp DESC;
```

## Rollback (If Needed)

### Drop all tables and start over
```bash
sudo -u postgres psql serversage -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
python main.py  # Recreates tables
```

### Restore from backup
```bash
psql -U serversage serversage < backup.sql
```

## Next Steps After Setup

1. **Monitor logs** for database errors during normal operation
2. **Set up automated backups** (see `docs/DATABASE_SETUP.md`)
3. **Review unmapped skills** periodically to add new roles
4. **Analyze role history** for insights

## Time Estimates

| Task | Time |
|------|------|
| Database setup | 5 min |
| Install dependencies | 2 min |
| Test connection | 1 min |
| Migrate verified users | 5-10 min |
| Migrate unmapped skills | 15-30 min |
| Verification tests | 5 min |
| **Total** | **~35-55 min** |

## Support

- **Full docs**: `docs/DATABASE_SETUP.md`
- **Implementation details**: `docs/DATABASE_IMPLEMENTATION_SUMMARY.md`
- **Logs**: Check `logs/` directory
- **Database errors**: Check PostgreSQL logs: `/var/log/postgresql/`

---

**Ready to start?** Begin with Step 1 above! 🚀
