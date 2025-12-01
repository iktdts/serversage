#!/usr/bin/env python3
# File: scripts/migrate_verified_users_roles.py

"""
Migration script to capture current roles of verified users and store them in the database.

This script:
1. Connects to Discord
2. Finds all members with the VERIFIED_ROLE_ID
3. Syncs all categorized roles to the database
4. Captures each verified member's current roles and stores them in assigned_roles table

Usage:
    python scripts/migrate_verified_users_roles.py
"""

import asyncio
import discord
import logging
import sys
from pathlib import Path

# Add parent directory to path so we can import from the project
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from database import init_engine, create_tables
from services.database_service import DatabaseService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MigrationBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.db_service = DatabaseService()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("=" * 60)

        try:
            await self.run_migration()
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
        finally:
            await self.close()

    async def run_migration(self):
        """Main migration logic."""
        if not self.guilds:
            logger.error("Bot is not in any guilds. Cannot proceed with migration.")
            return

        guild = self.guilds[0]
        logger.info(f"Running migration for guild: {guild.name} (ID: {guild.id})")

        # Get verified role
        verified_role = guild.get_role(settings.VERIFIED_ROLE_ID)
        if not verified_role:
            logger.error(
                f"Verified role with ID {settings.VERIFIED_ROLE_ID} not found in guild."
            )
            return

        logger.info(f"Verified role: {verified_role.name} (ID: {verified_role.id})")

        # Load categorized roles from file
        import json
        import os

        categorized_roles_file = settings.CATEGORIZED_ROLES_FILE
        if not os.path.exists(categorized_roles_file):
            logger.error(
                f"Categorized roles file not found: {categorized_roles_file}"
            )
            logger.error(
                "Please run the bot at least once to generate categorized roles."
            )
            return

        with open(categorized_roles_file, "r") as f:
            categorized_roles = json.load(f)

        logger.info(f"Loaded categorized roles from {categorized_roles_file}")

        # Build set of all managed role IDs
        all_managed_role_ids = set()
        for category, role_ids in categorized_roles.items():
            all_managed_role_ids.update(role_ids)

        logger.info(f"Found {len(all_managed_role_ids)} managed roles across all categories.")

        # Step 1: Sync all categorized roles to database
        logger.info("Step 1: Syncing all categorized roles to database...")
        roles_to_sync = []

        for category, role_ids in categorized_roles.items():
            for role_id in role_ids:
                role = guild.get_role(role_id)
                if role:
                    roles_to_sync.append(
                        {
                            "role_id": role.id,
                            "role_name": role.name,
                            "category": category,
                        }
                    )
                else:
                    logger.warning(
                        f"Role ID {role_id} from category '{category}' not found in guild. Skipping."
                    )

        if roles_to_sync:
            await self.db_service.sync_multiple_roles(roles_to_sync)
            logger.info(f"Synced {len(roles_to_sync)} roles to database.")
        else:
            logger.warning("No roles to sync.")

        # Step 2: Find all verified members
        logger.info("Step 2: Finding verified members...")
        verified_members = [m for m in guild.members if verified_role in m.roles]
        logger.info(f"Found {len(verified_members)} verified members.")

        if not verified_members:
            logger.info("No verified members found. Migration complete.")
            return

        # Step 3: Capture and store roles for each verified member
        logger.info("Step 3: Capturing roles for verified members...")

        migrated_count = 0
        skipped_count = 0

        for member in verified_members:
            if member.bot:
                logger.debug(f"Skipping bot: {member.name}")
                skipped_count += 1
                continue

            # Get member's managed roles
            member_managed_roles = []
            for role in member.roles:
                if role.id in all_managed_role_ids:
                    member_managed_roles.append(role.id)

            if not member_managed_roles:
                logger.debug(
                    f"Member {member.name} (ID: {member.id}) has no managed roles. Skipping."
                )
                skipped_count += 1
                continue

            # Store roles in database
            try:
                await self.db_service.assign_roles_to_user(
                    user_id=member.id,
                    role_ids=member_managed_roles,
                    assigned_by="migration",
                    clear_existing=False,  # Don't clear since this is initial migration
                )
                migrated_count += 1
                logger.info(
                    f"✓ Migrated {len(member_managed_roles)} roles for {member.name} (ID: {member.id})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to migrate roles for {member.name} (ID: {member.id}): {e}",
                    exc_info=True,
                )

        logger.info("=" * 60)
        logger.info(f"Migration Summary:")
        logger.info(f"  Total verified members: {len(verified_members)}")
        logger.info(f"  Successfully migrated: {migrated_count}")
        logger.info(f"  Skipped (no roles or bots): {skipped_count}")
        logger.info("=" * 60)
        logger.info("Migration complete!")


async def main():
    """Initialize database and run migration bot."""
    logger.info("Initializing database...")

    try:
        # Initialize database
        init_engine(settings.DATABASE_URL, echo=False)
        await create_tables()
        logger.info("Database initialized successfully.")

        # Run migration bot
        logger.info("Starting migration bot...")
        bot = MigrationBot()
        await bot.start(settings.DISCORD_BOT_TOKEN)

    except Exception as e:
        logger.error(f"Failed to run migration: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
