# File: database/models.py

from sqlalchemy import BigInteger, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from typing import Optional


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Role(Base):
    """
    Stores Discord roles with their metadata.
    This table is kept in sync with Discord server roles via event listeners.
    """
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_roles_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<Role(role_id={self.role_id}, role_name='{self.role_name}', category='{self.category}')>"


class AssignedRole(Base):
    """
    Stores the current role assignments for users.
    Each row represents one role assigned to one user.
    When roles are updated, old entries are moved to role_history before deletion.
    """
    __tablename__ = "assigned_roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_by: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "verification", "manual_assignment", "discord_event"

    __table_args__ = (
        Index("ix_assigned_roles_user_id", "user_id"),
        Index("ix_assigned_roles_role_id", "role_id"),
        Index("ix_assigned_roles_user_role", "user_id", "role_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<AssignedRole(user_id={self.user_id}, role_id={self.role_id}, assigned_by='{self.assigned_by}')>"


class RoleHistory(Base):
    """
    Stores historical changes to user role assignments.
    Records individual role additions and removals with the role name at the time of the operation.
    """
    __tablename__ = "role_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "added" or "removed"
    triggered_by: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "verification", "manual_assignment", "discord_event", "admin_change"
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_role_history_user_id", "user_id"),
        Index("ix_role_history_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<RoleHistory(user_id={self.user_id}, role_name='{self.role_name}', action='{self.action}', timestamp={self.timestamp})>"


class UnmappedSkill(Base):
    """
    Stores skills mentioned by users that couldn't be mapped to existing roles.
    This is a historical record - entries are only added, never updated.
    """
    __tablename__ = "unmapped_skills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_name: Mapped[str] = mapped_column(String(100), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(200), nullable=False)
    suggested_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mentioned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="verification"
    )  # "verification" or "migration"

    __table_args__ = (
        Index("ix_unmapped_skills_user_id", "user_id"),
        Index("ix_unmapped_skills_skill_name", "skill_name"),
        Index("ix_unmapped_skills_mentioned_at", "mentioned_at"),
    )

    def __repr__(self) -> str:
        return f"<UnmappedSkill(user_id={self.user_id}, skill_name='{self.skill_name}', suggested_category='{self.suggested_category}')>"


class UserPreference(Base):
    """Stores per-user preferences such as locale."""
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    preferred_locale: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<UserPreference(user_id={self.user_id}, preferred_locale='{self.preferred_locale}')>"
