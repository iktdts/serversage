# File: services/database_service.py

import logging
from typing import List, Dict, Optional, Set, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session, Role, AssignedRole, RoleHistory, UnmappedSkill

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Service layer for database operations related to roles and unmapped skills.
    """

    def __init__(self, bot=None, settings=None):
        """
        Initialize the DatabaseService.

        Args:
            bot: Discord bot instance (optional, for sending notifications)
            settings: Settings instance (optional, for notification channel)
        """
        self.bot = bot
        self.settings = settings

    async def _send_role_assignment_failure_notification(
        self,
        user_id: int,
        user_name: str,
        failed_role_ids: List[int],
        guild: Optional['discord.Guild'] = None
    ) -> None:
        """
        Send a notification to the admin channel about failed role assignments.

        Args:
            user_id: Discord user ID
            user_name: Discord username
            failed_role_ids: List of role IDs that failed to assign
            guild: Discord guild object (optional)
        """
        if not self.settings or not self.settings.NOTIFICATION_CHANNEL_ID:
            logger.debug("NOTIFICATION_CHANNEL_ID not set. Skipping role assignment failure notification.")
            return

        if not self.bot:
            logger.warning("Bot instance not available. Cannot send role assignment failure notification.")
            return

        try:
            import discord

            # Get the notification channel
            if guild:
                channel = guild.get_channel(self.settings.NOTIFICATION_CHANNEL_ID)
            else:
                channel = self.bot.get_channel(self.settings.NOTIFICATION_CHANNEL_ID)

            if not channel or not isinstance(channel, discord.TextChannel):
                logger.error(f"Invalid NOTIFICATION_CHANNEL_ID or channel not found: {self.settings.NOTIFICATION_CHANNEL_ID}")
                return

            # Build the message with role names
            async with get_session() as session:
                failed_roles_info = []
                for role_id in failed_role_ids:
                    role_name = await self._get_role_name(session, role_id)

                    # Try to get role from Discord
                    discord_role = None
                    if guild:
                        discord_role = guild.get_role(role_id)

                    if discord_role:
                        failed_roles_info.append(f"• **{role_name}** (ID: {role_id}) - exists in Discord")
                    else:
                        failed_roles_info.append(f"• **{role_name}** (ID: {role_id}) - missing from Discord or database")

            failed_roles_text = "\n".join(failed_roles_info)

            embed = discord.Embed(
                title="⚠️ Role Assignment Failure",
                description=f"Failed to assign some roles to user **{user_name}** (ID: {user_id})",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name="Failed Roles",
                value=failed_roles_text if failed_roles_text else "No details available",
                inline=False
            )
            embed.add_field(
                name="Action Required",
                value="Please verify that these roles exist in both Discord and the database. Use `/sync-roles` to sync roles.",
                inline=False
            )

            await channel.send(embed=embed)
            logger.info(f"Sent role assignment failure notification for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to send role assignment failure notification: {e}", exc_info=True)

    # ========== Role Management ==========

    async def sync_role(
        self, role_id: int, role_name: str, category: Optional[str] = None
    ) -> None:
        """
        Insert or update a role in the database.
        Uses INSERT ... ON CONFLICT to handle both new roles and updates.

        Args:
            role_id: Discord role ID
            role_name: Role name
            category: Role category (e.g., "Programming_Language", "Experience_Level")
        """
        async with get_session() as session:
            stmt = insert(Role).values(
                role_id=role_id,
                role_name=role_name,
                category=category,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["role_id"],
                set_={
                    "role_name": role_name,
                    "category": category,
                    "updated_at": datetime.utcnow(),
                },
            )
            await session.execute(stmt)
            await session.commit()
            logger.debug(f"Synced role {role_id} ({role_name}) to database.")

    async def sync_multiple_roles(
        self, roles: List[Dict[str, any]]
    ) -> None:
        """
        Sync multiple roles at once for better performance.

        Args:
            roles: List of dicts with keys: role_id, role_name, category (optional)
        """
        if not roles:
            return

        async with get_session() as session:
            for role_data in roles:
                stmt = insert(Role).values(
                    role_id=role_data["role_id"],
                    role_name=role_data["role_name"],
                    category=role_data.get("category"),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["role_id"],
                    set_={
                        "role_name": role_data["role_name"],
                        "category": role_data.get("category"),
                        "updated_at": datetime.utcnow(),
                    },
                )
                await session.execute(stmt)
            await session.commit()
            logger.info(f"Synced {len(roles)} roles to database.")

    async def delete_role(self, role_id: int) -> None:
        """
        Delete a role from the database.
        CASCADE will automatically remove associated assigned_roles entries.

        Args:
            role_id: Discord role ID to delete
        """
        async with get_session() as session:
            stmt = delete(Role).where(Role.role_id == role_id)
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount > 0:
                logger.info(f"Deleted role {role_id} from database.")
            else:
                logger.debug(f"Role {role_id} not found in database for deletion.")

    async def get_role(self, role_id: int) -> Optional[Role]:
        """
        Get a role by its ID.

        Args:
            role_id: Discord role ID

        Returns:
            Role object or None if not found
        """
        async with get_session() as session:
            stmt = select(Role).where(Role.role_id == role_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    # ========== Assigned Roles Management ==========

    async def get_user_assigned_roles(self, user_id: int) -> List[AssignedRole]:
        """
        Get all currently assigned roles for a user.

        Args:
            user_id: Discord user ID

        Returns:
            List of AssignedRole objects
        """
        async with get_session() as session:
            stmt = select(AssignedRole).where(AssignedRole.user_id == user_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def assign_roles_to_user(
        self,
        user_id: int,
        role_ids: List[int],
        assigned_by: str = "verification",
        clear_existing: bool = True,
    ) -> Dict[str, List[int]]:
        """
        Assign roles to a user. Optionally clears existing roles first and saves them to history.

        Args:
            user_id: Discord user ID
            role_ids: List of role IDs to assign
            assigned_by: Source of assignment ("verification", "manual_assignment", etc.)
            clear_existing: If True, remove existing roles and save to history before assigning new ones

        Returns:
            Dict with 'success' (list of successfully assigned role IDs) and 'failed' (list of failed role IDs)
        """
        result = {"success": [], "failed": []}

        async with get_session() as session:
            if clear_existing:
                # Get existing roles before clearing
                existing_stmt = select(AssignedRole).where(AssignedRole.user_id == user_id)
                existing_result = await session.execute(existing_stmt)
                existing_roles = list(existing_result.scalars().all())

                # Save to history before deletion
                if existing_roles:
                    await self._save_roles_to_history(
                        session, user_id, existing_roles, "removed", assigned_by
                    )

                # Delete existing assignments
                delete_stmt = delete(AssignedRole).where(AssignedRole.user_id == user_id)
                await session.execute(delete_stmt)
                logger.debug(f"Cleared {len(existing_roles)} existing roles for user {user_id}.")

            # Insert new role assignments - one at a time to handle partial failures
            if role_ids:
                for role_id in role_ids:
                    try:
                        # Check if role exists in roles table
                        role = await session.get(Role, role_id)
                        if not role:
                            logger.warning(f"Role {role_id} not found in roles table for user {user_id}")
                            result["failed"].append(role_id)
                            continue

                        new_assignment = AssignedRole(
                            user_id=user_id,
                            role_id=role_id,
                            assigned_at=datetime.utcnow(),
                            assigned_by=assigned_by,
                        )
                        session.add(new_assignment)

                        # Save to history for this specific role
                        await self._save_new_assignments_to_history(
                            session, user_id, [role_id], assigned_by
                        )

                        # Commit after each successful role to ensure partial success
                        await session.commit()
                        result["success"].append(role_id)
                        logger.debug(f"Successfully assigned role {role_id} to user {user_id}")

                    except Exception as e:
                        await session.rollback()
                        # Get role name for better logging
                        role_name = await self._get_role_name(session, role_id)
                        logger.error(
                            f"Failed to assign role {role_id} ({role_name}) to user {user_id}: {e}",
                            exc_info=True
                        )
                        result["failed"].append(role_id)

            logger.info(
                f"Assigned {len(result['success'])} roles to user {user_id} (assigned_by={assigned_by}). "
                f"Failed: {len(result['failed'])} roles."
            )
            return result

    async def add_role_to_user(
        self, user_id: int, role_id: int, assigned_by: str = "discord_event"
    ) -> bool:
        """
        Add a single role to a user without clearing existing roles.

        Args:
            user_id: Discord user ID
            role_id: Role ID to add
            assigned_by: Source of assignment

        Returns:
            True if successful, False if failed
        """
        async with get_session() as session:
            try:
                # Check if already assigned
                check_stmt = select(AssignedRole).where(
                    AssignedRole.user_id == user_id, AssignedRole.role_id == role_id
                )
                result = await session.execute(check_stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    logger.debug(f"Role {role_id} already assigned to user {user_id}. Skipping.")
                    return True

                # Check if role exists in roles table
                role = await session.get(Role, role_id)
                if not role:
                    role_name = await self._get_role_name(session, role_id)
                    logger.warning(f"Role {role_id} ({role_name}) not found in roles table for user {user_id}")
                    return False

                # Add new assignment
                new_assignment = AssignedRole(
                    user_id=user_id,
                    role_id=role_id,
                    assigned_at=datetime.utcnow(),
                    assigned_by=assigned_by,
                )
                session.add(new_assignment)

                # Save to history
                await self._save_new_assignments_to_history(
                    session, user_id, [role_id], assigned_by
                )

                await session.commit()
                logger.info(f"Added role {role_id} to user {user_id}.")
                return True
            except Exception as e:
                await session.rollback()
                role_name = await self._get_role_name(session, role_id)
                logger.error(
                    f"Failed to add role {role_id} ({role_name}) to user {user_id}: {e}",
                    exc_info=True
                )
                return False

    async def remove_role_from_user(
        self, user_id: int, role_id: int, triggered_by: str = "discord_event"
    ) -> None:
        """
        Remove a single role from a user.

        Args:
            user_id: Discord user ID
            role_id: Role ID to remove
            triggered_by: What triggered the removal
        """
        async with get_session() as session:
            # Get the assignment before deleting
            select_stmt = select(AssignedRole).where(
                AssignedRole.user_id == user_id, AssignedRole.role_id == role_id
            )
            result = await session.execute(select_stmt)
            assignment = result.scalar_one_or_none()

            if not assignment:
                logger.debug(f"Role {role_id} not assigned to user {user_id}. Nothing to remove.")
                return

            # Save to history
            await self._save_roles_to_history(
                session, user_id, [assignment], "removed", triggered_by
            )

            # Delete the assignment
            delete_stmt = delete(AssignedRole).where(
                AssignedRole.user_id == user_id, AssignedRole.role_id == role_id
            )
            await session.execute(delete_stmt)
            await session.commit()
            logger.info(f"Removed role {role_id} from user {user_id}.")

    async def _save_roles_to_history(
        self,
        session: AsyncSession,
        user_id: int,
        assignments: List[AssignedRole],
        action: str,
        triggered_by: str,
    ) -> None:
        """
        Internal helper to save role assignments to history.

        Args:
            session: Active database session
            user_id: Discord user ID
            assignments: List of AssignedRole objects
            action: "added" or "removed"
            triggered_by: What triggered the change
        """
        history_entries = []
        for assignment in assignments:
            # Get role name from database
            role = await session.get(Role, assignment.role_id)
            role_name = role.role_name if role else f"Unknown Role ({assignment.role_id})"

            history_entries.append(
                RoleHistory(
                    user_id=user_id,
                    role_name=role_name,
                    action=action,
                    triggered_by=triggered_by,
                    timestamp=datetime.utcnow(),
                )
            )

        if history_entries:
            session.add_all(history_entries)
            logger.debug(
                f"Saved {len(history_entries)} role history entries for user {user_id}."
            )

    async def _save_new_assignments_to_history(
        self,
        session: AsyncSession,
        user_id: int,
        role_ids: List[int],
        assigned_by: str,
    ) -> None:
        """
        Internal helper to save new role assignments to history.

        Args:
            session: Active database session
            user_id: Discord user ID
            role_ids: List of role IDs being assigned
            assigned_by: Source of assignment
        """
        history_entries = []
        for role_id in role_ids:
            role = await session.get(Role, role_id)
            role_name = role.role_name if role else f"Unknown Role ({role_id})"

            history_entries.append(
                RoleHistory(
                    user_id=user_id,
                    role_name=role_name,
                    action="added",
                    triggered_by=assigned_by,
                    timestamp=datetime.utcnow(),
                )
            )

        if history_entries:
            session.add_all(history_entries)
            logger.debug(
                f"Saved {len(history_entries)} role history entries (added) for user {user_id}."
            )

    async def _get_role_name(self, session: AsyncSession, role_id: int) -> str:
        """
        Internal helper to get role name from database or return a placeholder.

        Args:
            session: Active database session
            role_id: Role ID to look up

        Returns:
            Role name or "Unknown Role (ID)" if not found
        """
        try:
            role = await session.get(Role, role_id)
            return role.role_name if role else f"Unknown Role ({role_id})"
        except Exception:
            return f"Unknown Role ({role_id})"

    # ========== Role History ==========

    async def get_user_role_history(
        self, user_id: int, limit: Optional[int] = None
    ) -> List[RoleHistory]:
        """
        Get role history for a user, ordered by timestamp descending.

        Args:
            user_id: Discord user ID
            limit: Maximum number of entries to return

        Returns:
            List of RoleHistory objects
        """
        async with get_session() as session:
            stmt = (
                select(RoleHistory)
                .where(RoleHistory.user_id == user_id)
                .order_by(RoleHistory.timestamp.desc())
            )
            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ========== Unmapped Skills ==========

    async def save_unmapped_skill(
        self,
        user_id: int,
        user_name: str,
        skill_name: str,
        suggested_category: Optional[str] = None,
        source: str = "verification",
    ) -> None:
        """
        Save an unmapped skill to the database.

        Args:
            user_id: Discord user ID
            user_name: Discord username
            skill_name: Name of the skill
            suggested_category: Suggested category for the skill
            source: Where this came from ("verification" or "migration")
        """
        async with get_session() as session:
            unmapped_skill = UnmappedSkill(
                user_id=user_id,
                user_name=user_name,
                skill_name=skill_name,
                suggested_category=suggested_category,
                mentioned_at=datetime.utcnow(),
                source=source,
            )
            session.add(unmapped_skill)
            await session.commit()
            logger.info(
                f"Saved unmapped skill '{skill_name}' for user {user_id} ({user_name})."
            )

    async def save_unmapped_skills_batch(
        self, skills: List[Dict[str, any]]
    ) -> None:
        """
        Save multiple unmapped skills at once.

        Args:
            skills: List of dicts with keys: user_id, user_name, skill_name, 
                    suggested_category (optional), source (optional), mentioned_at (optional)
        """
        if not skills:
            return

        async with get_session() as session:
            skill_objects = []
            for skill_data in skills:
                skill_objects.append(
                    UnmappedSkill(
                        user_id=skill_data["user_id"],
                        user_name=skill_data["user_name"],
                        skill_name=skill_data["skill_name"],
                        suggested_category=skill_data.get("suggested_category"),
                        mentioned_at=skill_data.get("mentioned_at", datetime.utcnow()),
                        source=skill_data.get("source", "migration"),
                    )
                )
            session.add_all(skill_objects)
            await session.commit()
            logger.info(f"Saved {len(skill_objects)} unmapped skills in batch.")

    async def get_unmapped_skills_by_user(self, user_id: int) -> List[UnmappedSkill]:
        """
        Get all unmapped skills for a specific user.

        Args:
            user_id: Discord user ID

        Returns:
            List of UnmappedSkill objects
        """
        async with get_session() as session:
            stmt = (
                select(UnmappedSkill)
                .where(UnmappedSkill.user_id == user_id)
                .order_by(UnmappedSkill.mentioned_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_all_unmapped_skills(self) -> List[UnmappedSkill]:
        """
        Get all unmapped skills from the database.

        Returns:
            List of UnmappedSkill objects
        """
        async with get_session() as session:
            stmt = select(UnmappedSkill).order_by(UnmappedSkill.mentioned_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())
