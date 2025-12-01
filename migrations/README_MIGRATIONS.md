# Database Migrations

This folder contains all database migration scripts and Docker configuration for the ServerSage Discord bot.

## Files

- `Dockerfile` - Docker image for running migrations
- `docker-compose.yml` - Docker Compose configuration for migration services
- `run_migrations.sh` - Interactive helper script to run migrations
- `migrate_verified_users_roles.py` - Automated migration for verified users' current roles
- `migrate_unmapped_skills.py` - Interactive migration for historical unmapped skills
- `setup_database.sh` - Database initialization script

## Quick Start

From the migrations folder, run the interactive helper:

```bash
cd migrations
./run_migrations.sh
```

## Manual Migration Commands

From the migrations folder:

### Build migration image:
```bash
docker compose build
```

### Migrate verified users (automated):
```bash
docker compose run --rm migrate_verified_users
```

### Migrate unmapped skills (interactive):
```bash
docker compose run --rm migrate_unmapped_skills
```

## Prerequisites

1. **Docker networks exist:**
   ```bash
   docker network create dbnet
   docker network create bot
   ```

2. **Secrets files exist:**
   - `../secrets/discord_token.txt`
   - `../secrets/db_password.txt`

3. **Database configuration in `../.env`:**
   - DATABASE_HOST
   - DATABASE_PORT
   - DATABASE_NAME
   - DATABASE_USER

## File Structure

```
migrations/
├── Dockerfile                         # Docker image definition
├── docker-compose.yml                 # Compose config (builds from parent dir)
├── run_migrations.sh                  # Interactive helper
├── migrate_verified_users_roles.py    # Migration script 1
├── migrate_unmapped_skills.py         # Migration script 2
└── setup_database.sh                  # Local DB setup helper
```

## How It Works

The Docker Compose file:
- **Context**: `..` (parent directory - project root)
- **Dockerfile**: `migrations/Dockerfile`
- **Networks**: Connects to `dbnet` and `bot`
- **Secrets**: Mounts Discord token and DB password
- **Env File**: Uses `../.env` from project root

This allows the migration containers to:
- Access the full project code (from parent directory)
- Connect to your PostgreSQL database via `dbnet`
- Use the same configuration as the main bot

## Documentation

See `../docs/DOCKER_MIGRATIONS.md` for complete documentation including:
- Detailed setup instructions
- Troubleshooting guide
- Advanced usage examples
- Testing database connections

## Notes

- Run all commands from **within the migrations folder**
- Migration containers are built from the **project root** (parent directory)
- All paths in `docker-compose.yml` use `..` to reference project root
- The `run_migrations.sh` script automatically handles directory context
- This keeps all migration-related files organized in one place

---

**Need help?** Run `./run_migrations.sh` and follow the interactive prompts!
