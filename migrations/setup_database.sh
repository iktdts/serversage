#!/bin/bash
# File: scripts/setup_database.sh
# Quick database setup script for ServerSage

set -e  # Exit on error

echo "=========================================="
echo "ServerSage Database Setup"
echo "=========================================="
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed."
    echo ""
    echo "Install PostgreSQL:"
    echo "  Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
    echo "  macOS:         brew install postgresql@15"
    echo ""
    exit 1
fi

echo "✓ PostgreSQL is installed"
echo ""

# Get database configuration
read -p "Database name [serversage]: " DB_NAME
DB_NAME=${DB_NAME:-serversage}

read -p "Database user [serversage]: " DB_USER
DB_USER=${DB_USER:-serversage}

read -sp "Database password: " DB_PASSWORD
echo ""

read -p "Database host [localhost]: " DB_HOST
DB_HOST=${DB_HOST:-localhost}

read -p "Database port [5432]: " DB_PORT
DB_PORT=${DB_PORT:-5432}

echo ""
echo "Creating database and user..."
echo ""

# Create database and user
sudo -u postgres psql <<EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

\c $DB_NAME

-- Grant privileges on schema
GRANT ALL PRIVILEGES ON SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;

-- Grant future privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

echo ""
echo "✓ Database created successfully"
echo ""

# Update .env file
ENV_FILE=".env"

if [ -f "$ENV_FILE" ]; then
    echo "Updating $ENV_FILE..."
    
    # Backup existing .env
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Remove old database config if exists
    sed -i '/^DATABASE_HOST=/d' "$ENV_FILE"
    sed -i '/^DATABASE_PORT=/d' "$ENV_FILE"
    sed -i '/^DATABASE_NAME=/d' "$ENV_FILE"
    sed -i '/^DATABASE_USER=/d' "$ENV_FILE"
    sed -i '/^DATABASE_PASSWORD=/d' "$ENV_FILE"
    
    # Add new database config
    cat >> "$ENV_FILE" <<EOF

# Database Configuration (added by setup_database.sh)
DATABASE_HOST=$DB_HOST
DATABASE_PORT=$DB_PORT
DATABASE_NAME=$DB_NAME
DATABASE_USER=$DB_USER
DATABASE_PASSWORD=$DB_PASSWORD
EOF
    
    echo "✓ Updated $ENV_FILE"
else
    echo "⚠️  .env file not found. Please create it manually with:"
    echo ""
    echo "DATABASE_HOST=$DB_HOST"
    echo "DATABASE_PORT=$DB_PORT"
    echo "DATABASE_NAME=$DB_NAME"
    echo "DATABASE_USER=$DB_USER"
    echo "DATABASE_PASSWORD=$DB_PASSWORD"
fi

echo ""
echo "Testing database connection..."

if PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT 1;" &> /dev/null; then
    echo "✓ Database connection successful"
else
    echo "❌ Database connection failed"
    echo "Please check your configuration and try again"
    exit 1
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Install Python dependencies: pip install -r requirements.txt"
echo "  2. Run the bot to create tables: python main.py"
echo "  3. Run migrations:"
echo "     - Migrate verified users: python scripts/migrate_verified_users_roles.py"
echo "     - Migrate unmapped skills: python scripts/migrate_unmapped_skills.py"
echo ""
echo "See docs/DATABASE_SETUP.md for more information"
echo ""
