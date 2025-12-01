#!/bin/bash
# File: migrations/run_migrations.sh
# Helper script to run database migrations in Docker

set -e

# Change to project root directory
cd "$(dirname "$0")/.."

echo "=========================================="
echo "ServerSage Database Migrations (Docker)"
echo "=========================================="
echo ""

# Function to check if network exists
check_network() {
    local network=$1
    if ! docker network inspect "$network" &> /dev/null; then
        echo "❌ Network '$network' does not exist."
        echo ""
        echo "Create it with:"
        echo "  docker network create $network"
        echo ""
        return 1
    fi
    return 0
}

# Function to check if secrets exist
check_secrets() {
    local missing=0
    
    if [ ! -f "./secrets/discord_token.txt" ]; then
        echo "❌ ./secrets/discord_token.txt not found"
        missing=1
    fi
    
    if [ ! -f "./secrets/db_password.txt" ]; then
        echo "❌ ./secrets/db_password.txt not found"
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        echo ""
        echo "Please create the required secret files:"
        echo "  echo 'your_discord_token' > ./secrets/discord_token.txt"
        echo "  echo 'your_db_password' > ./secrets/db_password.txt"
        echo ""
        return 1
    fi
    
    return 0
}

# Check prerequisites
echo "Checking prerequisites..."

if ! check_network "dbnet"; then
    exit 1
fi

if ! check_network "bot"; then
    exit 1
fi

if ! check_secrets; then
    exit 1
fi

echo "✓ Prerequisites OK"
echo ""

# Show menu
echo "Select migration to run:"
echo ""
echo "  1) Migrate verified users roles (automated, ~5 min)"
echo "  2) Migrate unmapped skills (interactive, ~15-30 min)"
echo "  3) Run both migrations (users first, then skills)"
echo "  4) Exit"
echo ""

read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo ""
        run_verified_users_migration() {
    echo ""
    echo "========================================="
    echo "Running Verified Users Migration"
    echo "========================================="
    echo ""
    docker compose -f migrations/docker-compose.yml run --rm migrate_verified_users
    echo ""
    echo "Migration completed!"
}
        ;;
        
    2)
        echo ""
        echo "=========================================="
        echo "Running Unmapped Skills Migration"
        echo "=========================================="
        echo ""
        echo "⚠️  This is an INTERACTIVE migration."
        echo "You will be prompted to validate each batch."
        echo ""
        read -p "Continue? (yes/no): " confirm
        
        if [[ ! "$confirm" =~ ^[Yy]([Ee][Ss])?$ ]]; then
            echo "Migration cancelled."
            exit 0
        fi
        
        echo ""
        echo "Building migration container..."
        docker compose -f migrations/docker-compose.yml build migrate_unmapped_skills
        
        echo ""
        echo "Starting interactive migration..."
        docker compose -f migrations/docker-compose.yml run --rm migrate_unmapped_skills
        
        echo ""
        echo "✓ Unmapped skills migration complete!"
        ;;
        
    3)
        echo ""
        echo "=========================================="
        echo "Running Both Migrations"
        echo "=========================================="
        echo ""
        
        # Build both containers
        echo "Building migration containers..."
        docker compose -f migrations/docker-compose.yml build
        
        # Run verified users first
        echo ""
        echo "Step 1/2: Migrating verified users..."
        docker compose -f migrations/docker-compose.yml run --rm migrate_verified_users
        
        echo ""
        echo "✓ Verified users migration complete!"
        echo ""
        
        # Run unmapped skills
        echo "Step 2/2: Migrating unmapped skills (interactive)..."
        echo ""
        read -p "Continue to interactive migration? (yes/no): " confirm
        
        if [[ "$confirm" =~ ^[Yy]([Ee][Ss])?$ ]]; then
            docker compose -f migrations/docker-compose.yml run --rm migrate_unmapped_skills
            echo ""
            echo "✓ Both migrations complete!"
        else
            echo "Skipped unmapped skills migration."
            echo "You can run it later with:"
            echo "  ./migrations/run_migrations.sh"
        fi
        ;;
        
    4)
        echo "Exiting."
        exit 0
        ;;
        
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "All Done!"
echo "=========================================="
echo ""
echo "You can now start the bot with:"
echo "  docker compose up -d"
echo ""
