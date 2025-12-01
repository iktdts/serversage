# File: cogs/role_sync_cog.py

import discord
from discord.ext import commands, tasks
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RoleSyncCog(commands.Cog, name="RoleSync"):
    """
    Listens to Discord role events and member role updates to keep the database in sync.
    Also includes periodic sync to ensure consistency.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings = bot.settings
        self.db_service = getattr(bot, "db_service", None)

        # Configure the periodic sync interval from settings
        sync_interval = getattr(self.settings, 'ROLE_SYNC_INTERVAL_MINUTES', 30)
        self.periodic_role_sync.change_interval(minutes=sync_interval)

        # Start the periodic sync task
        if not self.periodic_role_sync.is_running():
            self.periodic_role_sync.start()

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.periodic_role_sync.cancel()

    def _get_role_category(self, role_id: int) -> Optional[str]:
        """Get the category for a role from bot.categorized_server_roles."""
        if not self.bot.categorized_server_roles:
            return None

        for category, role_ids in self.bot.categorized_server_roles.items():
            if role_id in role_ids:
                return category
        return None

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """
        Called when a new role is created in the guild.
        """
        if not self.db_service:
            logger.warning("Database service not available. Skipping role create sync.")
            return

        logger.info(f"Role created: {role.name} (ID: {role.id})")

        try:
            # Get category if this role is in categorized_server_roles
            category = self._get_role_category(role.id)

            await self.db_service.sync_role(
                role_id=role.id,
                role_name=role.name,
                category=category,
            )
        except Exception as e:
            logger.error(f"Failed to sync newly created role {role.id} to database: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """
        Called when a role is deleted from the guild.
        This will cascade delete all assigned_roles entries due to foreign key constraint.
        """
        if not self.db_service:
            logger.warning("Database service not available. Skipping role delete sync.")
            return

        logger.info(f"Role deleted: {role.name} (ID: {role.id})")

        try:
            await self.db_service.delete_role(role_id=role.id)

            # Update categorized_server_roles if this role was tracked
            if self.bot.categorized_server_roles:
                for category, role_ids in self.bot.categorized_server_roles.items():
                    if role.id in role_ids:
                        role_ids.remove(role.id)
                        logger.info(f"Removed role {role.id} from category '{category}' in memory.")

            # Update server_roles_map
            if self.bot.server_roles_map and role.id in self.bot.server_roles_map:
                del self.bot.server_roles_map[role.id]
                logger.debug(f"Removed role {role.id} from server_roles_map.")

        except Exception as e:
            logger.error(f"Failed to delete role {role.id} from database: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """
        Called when a role is updated (renamed, permissions changed, etc.).
        We mainly care about name changes.
        """
        if not self.db_service:
            logger.warning("Database service not available. Skipping role update sync.")
            return

        # Only sync if the name changed
        if before.name != after.name:
            logger.info(f"Role renamed: '{before.name}' -> '{after.name}' (ID: {after.id})")

            try:
                category = self._get_role_category(after.id)

                await self.db_service.sync_role(
                    role_id=after.id,
                    role_name=after.name,
                    category=category,
                )

                # Update server_roles_map
                if self.bot.server_roles_map and after.id in self.bot.server_roles_map:
                    self.bot.server_roles_map[after.id] = after.name
                    logger.debug(f"Updated role name in server_roles_map: {after.id} -> '{after.name}'")

            except Exception as e:
                logger.error(f"Failed to sync role update for {after.id} to database: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Called when a member is updated (roles changed, nickname changed, etc.).
        We track role additions and removals to keep assigned_roles table in sync.
        Only tracks roles that are in categorized_server_roles.
        """
        if not self.db_service:
            return

        # Get role IDs before and after
        before_role_ids = {role.id for role in before.roles}
        after_role_ids = {role.id for role in after.roles}

        # Find roles that were added or removed
        added_role_ids = after_role_ids - before_role_ids
        removed_role_ids = before_role_ids - after_role_ids

        # Filter to only categorized roles (roles we manage)
        if self.bot.categorized_server_roles:
            all_managed_role_ids = set()
            for role_ids in self.bot.categorized_server_roles.values():
                all_managed_role_ids.update(role_ids)

            added_role_ids = added_role_ids & all_managed_role_ids
            removed_role_ids = removed_role_ids & all_managed_role_ids

        # Process additions
        for role_id in added_role_ids:
            try:
                success = await self.db_service.add_role_to_user(
                    user_id=after.id,
                    role_id=role_id,
                    assigned_by="discord_event",
                )
                if success:
                    logger.info(f"Member {after.name} gained role {role_id} via Discord event.")
                else:
                    logger.warning(f"Failed to add role {role_id} to user {after.id} in database (not in roles table)")
                    # Send notification for this failure
                    await self.db_service._send_role_assignment_failure_notification(
                        user_id=after.id,
                        user_name=after.name,
                        failed_role_ids=[role_id],
                        guild=after.guild
                    )
            except Exception as e:
                logger.error(
                    f"Failed to add role {role_id} to user {after.id} in database: {e}",
                    exc_info=True,
                )

        # Process removals
        for role_id in removed_role_ids:
            try:
                await self.db_service.remove_role_from_user(
                    user_id=after.id,
                    role_id=role_id,
                    triggered_by="discord_event",
                )
                logger.info(f"Member {after.name} lost role {role_id} via Discord event.")
            except Exception as e:
                logger.error(
                    f"Failed to remove role {role_id} from user {after.id} in database: {e}",
                    exc_info=True,
                )

    @tasks.loop(minutes=30)
    async def periodic_role_sync(self):
        """
        Periodically syncs all categorized roles from Discord to the database.
        This ensures consistency even if events are missed.
        """
        if not self.db_service:
            logger.debug("Database service not available. Skipping periodic role sync.")
            return

        try:
            # Get all guilds the bot is in
            for guild in self.bot.guilds:
                categorized_roles = getattr(self.bot, 'categorized_server_roles', {})
                if not categorized_roles:
                    logger.debug(f"No categorized roles for guild {guild.name}. Skipping periodic sync.")
                    continue

                # Build list of roles to sync
                roles_to_sync = []
                for category, role_ids in categorized_roles.items():
                    for role_id in role_ids:
                        discord_role = guild.get_role(role_id)
                        if discord_role:
                            roles_to_sync.append({
                                "role_id": discord_role.id,
                                "role_name": discord_role.name,
                                "category": category
                            })

                if roles_to_sync:
                    await self.db_service.sync_multiple_roles(roles_to_sync)
                    logger.info(f"Periodic sync: Synced {len(roles_to_sync)} roles for guild {guild.name}")

        except Exception as e:
            logger.error(f"Error during periodic role sync: {e}", exc_info=True)

    @periodic_role_sync.before_loop
    async def before_periodic_sync(self):
        """Wait until the bot is ready before starting the periodic sync."""
        await self.bot.wait_until_ready()
        logger.info(f"Periodic role sync task started. Will run every {self.settings.ROLE_SYNC_INTERVAL_MINUTES} minutes.")


async def setup(bot: commands.Bot):
    """Required setup function for the cog."""
    await bot.add_cog(RoleSyncCog(bot))
    logger.info("RoleSyncCog loaded successfully.")
