#!/usr/bin/env python3
# File: scripts/migrate_unmapped_skills.py

"""
Interactive migration script to scan historical "Unmappable Skill Alert" messages
and store them in the database.

This script:
1. Connects to Discord
2. Scans the UNMAPPED_SKILLS_CHANNEL_ID for messages with "🔔 Unmappable Skill Alert" embeds
3. Extracts user info and skill details from embed fields
4. Processes in batches with user validation
5. Stores validated data in unmapped_skills table

Usage:
    python scripts/migrate_unmapped_skills.py
"""

import asyncio
import discord
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

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

# Thread pool for async input
_input_executor = ThreadPoolExecutor(max_workers=1)


async def async_input(prompt: str) -> str:
    """
    Async wrapper for input() to avoid blocking the event loop.
    Runs input() in a separate thread.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_input_executor, input, prompt)


class UnmappedSkillMigration:
    """Handles the migration of unmapped skills from Discord messages."""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.total_messages_scanned = 0
        self.total_alerts_found = 0
        self.total_skills_migrated = 0

    def extract_skill_from_embed(
        self, embed: discord.Embed, message: discord.Message
    ) -> Optional[Dict[str, any]]:
        """
        Extract skill information from an "Unmappable Skill Alert" embed.

        Expected embed format:
        - Title: "🔔 Unmappable Skill Alert"
        - Fields:
            - User Name: <username>
            - Skill Mentioned: <skill>
            - Suggested Category: <category>

        Returns:
            Dict with user_id, user_name, skill_name, suggested_category, mentioned_at
            or None if extraction fails
        """
        if not embed.title or "Unmappable Skill Alert" not in embed.title:
            return None

        # Extract fields from embed
        user_name = None
        skill_name = None
        suggested_category = None

        for field in embed.fields:
            field_name = field.name.strip()
            field_value = field.value.strip()

            if "User Name" in field_name:
                user_name = field_value
            elif "Skill Mentioned" in field_name:
                skill_name = field_value
            elif "Suggested Category" in field_name:
                suggested_category = field_value

        # Validate we got required fields
        if not user_name or not skill_name:
            logger.warning(
                f"Incomplete embed data in message {message.id}. User: {user_name}, Skill: {skill_name}"
            )
            return None

        # Try to resolve user_id from mentions or search guild
        # Note: Old embeds may not have mentions, so we might only have the username
        user_id = 0  # Placeholder if we can't find the actual user ID

        # Check if there are any mentions in the message
        if message.mentions:
            # Assume the first mention is the user
            user_id = message.mentions[0].id
            logger.debug(f"Resolved user ID {user_id} from message mentions.")
        else:
            # Try to search guild members by name
            # This is a best-effort approach and may not always work
            logger.debug(
                f"No mentions found. User ID will be set to 0 for user: {user_name}"
            )

        return {
            "user_id": user_id,
            "user_name": user_name,
            "skill_name": skill_name,
            "suggested_category": suggested_category,
            "mentioned_at": message.created_at.replace(tzinfo=None),  # Convert to naive datetime
        }

    async def process_batch(
        self, messages: List[discord.Message]
    ) -> List[Dict[str, any]]:
        """
        Process a batch of messages and extract unmapped skills.

        Args:
            messages: List of Discord messages to process

        Returns:
            List of extracted skill dicts
        """
        extracted_skills = []

        for message in messages:
            self.total_messages_scanned += 1

            # Check if message has embeds
            if not message.embeds:
                continue

            # Process each embed in the message
            for embed in message.embeds:
                skill_data = self.extract_skill_from_embed(embed, message)
                if skill_data:
                    extracted_skills.append(skill_data)
                    self.total_alerts_found += 1

        return extracted_skills

    def display_skills(self, skills: List[Dict[str, any]]):
        """Display extracted skills in a readable format."""
        if not skills:
            print("\n  No unmappable skill alerts found in this batch.\n")
            return

        print(f"\n  Found {len(skills)} unmappable skill alert(s) in this batch:")
        print("  " + "=" * 70)

        for i, skill in enumerate(skills, 1):
            print(f"\n  {i}. User: {skill['user_name']} (ID: {skill['user_id']})")
            print(f"     Skill: {skill['skill_name']}")
            print(f"     Category: {skill['suggested_category']}")
            print(f"     Mentioned: {skill['mentioned_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}")

        print("\n  " + "=" * 70)

    async def save_skills(self, skills: List[Dict[str, any]]):
        """Save extracted skills to database."""
        if not skills:
            return

        # Add source field
        for skill in skills:
            skill["source"] = "migration"

        await self.db_service.save_unmapped_skills_batch(skills)
        self.total_skills_migrated += len(skills)
        logger.info(f"Saved {len(skills)} unmapped skills to database.")


class MigrationBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.db_service = DatabaseService()
        self.migration = UnmappedSkillMigration(self.db_service)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("=" * 70)

        try:
            await self.run_migration()
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
        finally:
            await self.close()

    async def run_migration(self):
        """Main migration logic with interactive batch processing."""
        if not self.guilds:
            logger.error("Bot is not in any guilds. Cannot proceed with migration.")
            return

        guild = self.guilds[0]
        logger.info(f"Running migration for guild: {guild.name} (ID: {guild.id})")

        # Get the unmapped skills channel
        if not settings.UNMAPPED_SKILLS_CHANNEL_ID:
            logger.error("UNMAPPED_SKILLS_CHANNEL_ID is not set in .env file.")
            return

        channel = guild.get_channel(settings.UNMAPPED_SKILLS_CHANNEL_ID)
        if not channel:
            logger.error(
                f"Channel with ID {settings.UNMAPPED_SKILLS_CHANNEL_ID} not found in guild."
            )
            return

        logger.info(f"Scanning channel: #{channel.name} (ID: {channel.id})")
        logger.info("=" * 70)

        # Configuration for batch processing
        BATCH_SIZE = 250  # Increased from 100 to 250
        batch_count = 0
        continue_scanning = True

        print("\nStarting interactive migration...")
        print(f"Batch size: {BATCH_SIZE} messages per batch\n")

        # Iterate through message history in batches
        last_message_id = None

        while continue_scanning:
            batch_count += 1
            print(f"\n{'=' * 70}")
            print(f"Batch {batch_count}: Fetching next {BATCH_SIZE} messages...")
            print('=' * 70)

            try:
                # Fetch messages
                messages = []
                async for message in channel.history(
                    limit=BATCH_SIZE, before=last_message_id and discord.Object(last_message_id)
                ):
                    messages.append(message)

                if not messages:
                    print("\n✓ No more messages to scan. Reached the end of channel history.")
                    break

                # Update last_message_id for next batch
                last_message_id = messages[-1].id

                # Process the batch
                extracted_skills = await self.migration.process_batch(messages)

                # Display results
                self.migration.display_skills(extracted_skills)

                # Ask user for validation
                if extracted_skills:
                    while True:
                        response = (await async_input(
                            "\n  Do you want to save these skills to the database? (yes/no/quit): "
                        )).strip().lower()

                        if response in ["yes", "y"]:
                            await self.migration.save_skills(extracted_skills)
                            print(f"  ✓ Saved {len(extracted_skills)} skills to database.\n")
                            break
                        elif response in ["no", "n"]:
                            print("  ✗ Skipped saving this batch.\n")
                            break
                        elif response in ["quit", "q", "exit"]:
                            print("\n  Migration stopped by user.")
                            continue_scanning = False
                            break
                        else:
                            print("  Invalid input. Please enter 'yes', 'no', or 'quit'.")

                if not continue_scanning:
                    break

                # Ask if user wants to continue to next batch
                while True:
                    response = (await async_input(
                        f"\n  Continue to next batch? (yes/no): "
                    )).strip().lower()

                    if response in ["yes", "y"]:
                        break
                    elif response in ["no", "n", "quit", "q"]:
                        print("\n  Migration stopped by user.")
                        continue_scanning = False
                        break
                    else:
                        print("  Invalid input. Please enter 'yes' or 'no'.")

            except discord.Forbidden:
                logger.error(f"Permission denied to read messages in channel #{channel.name}")
                break
            except Exception as e:
                logger.error(f"Error processing batch {batch_count}: {e}", exc_info=True)
                response = (await async_input("\n  An error occurred. Continue? (yes/no): ")).strip().lower()
                if response not in ["yes", "y"]:
                    break

        # Print summary
        print("\n" + "=" * 70)
        print("Migration Summary:")
        print("=" * 70)
        print(f"  Total messages scanned: {self.migration.total_messages_scanned}")
        print(f"  Total alerts found: {self.migration.total_alerts_found}")
        print(f"  Total skills migrated: {self.migration.total_skills_migrated}")
        print("=" * 70)
        print("Migration complete!")


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
