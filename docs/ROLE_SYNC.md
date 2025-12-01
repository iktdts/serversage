# Role Synchronization

This document explains how role synchronization between Discord and the database works in ServerSage.

## Overview

The bot maintains role information in a PostgreSQL database to track user role assignments, history, and analytics. To ensure consistency, roles must be synchronized between Discord and the database.

## Synchronization Methods

### 1. Real-time Event-Based Sync

The bot automatically syncs roles in real-time when Discord events occur:

- **Role Created**: When a new role is created in Discord, it's automatically added to the database
- **Role Updated**: When a role is renamed, the database is updated
- **Role Deleted**: When a role is deleted in Discord, it's removed from the database (cascade deletes all assignments)
- **Member Role Changes**: When a user gains or loses a role, the database is updated

**Location**: [cogs/role_sync_cog.py](../cogs/role_sync_cog.py)

### 2. Periodic Automatic Sync

A background task runs periodically to sync all categorized roles from Discord to the database. This ensures consistency even if events are missed.

**Configuration**:
```env
ROLE_SYNC_INTERVAL_MINUTES=30  # Default: 30 minutes
```

Set this in your `.env` file to control how often the automatic sync runs.

**Location**: [cogs/role_sync_cog.py](../cogs/role_sync_cog.py:191-232)

### 3. Manual Admin Command

Admins can manually trigger a full sync at any time:

```
/admin sync-roles
```

This command:
- Syncs all categorized roles from Discord to the database
- Provides a summary of synced roles by category
- Sends a notification to the admin channel

**Location**: [cogs/admin_commands_cog.py](../cogs/admin_commands_cog.py:277-355)

## When to Sync Roles

### Initial Setup

After deploying the bot or setting up the database for the first time:
1. Run `/admin rebuild-role-categories` to categorize roles
2. Run `/admin sync-roles` to sync all roles to the database

### After Role Changes

The bot automatically handles most scenarios, but you may want to manually sync if:
- You added many new roles at once
- You suspect the database is out of sync
- You're troubleshooting role assignment issues

### Regular Maintenance

The periodic sync (every 30 minutes by default) handles regular maintenance automatically. No manual intervention is needed.

## Foreign Key Violation Fixes

The original issue this system addresses:

```
ForeignKeyViolationError: insert or update on table "assigned_roles"
violates foreign key constraint "assigned_roles_role_id_fkey"
DETAIL: Key (role_id)=(1425163673835536484) is not present in table "roles".
```

**Solutions implemented**:

1. **Proper Error Logging**: Role names are included in all error messages
2. **Partial Assignment**: Valid roles are assigned even if some fail
3. **Admin Notifications**: Failed assignments trigger notifications to admin channel
4. **Automatic Sync**: Periodic sync ensures roles exist in database before assignment attempts

## Notification System

When role assignments fail, admins receive notifications in the configured `NOTIFICATION_CHANNEL_ID`:

**Notification includes**:
- User information (name and ID)
- List of failed roles with their names and IDs
- Whether each role exists in Discord vs database
- Suggested action: `/admin sync-roles`

**Example notification**:
```
⚠️ Role Assignment Failure
Failed to assign some roles to user JohnDoe (ID: 123456789)

Failed Roles:
• Python (ID: 1425163673835536484) - missing from Discord or database
• Java (ID: 987654321) - exists in Discord

Action Required:
Please verify that these roles exist in both Discord and the database.
Use /admin sync-roles to sync roles.
```

## Configuration

Add these settings to your `.env` file:

```env
# Role sync interval (in minutes)
ROLE_SYNC_INTERVAL_MINUTES=30

# Notification channel for alerts
NOTIFICATION_CHANNEL_ID=1234567890
```

## Troubleshooting

### Roles not syncing

1. Check logs for errors during sync
2. Verify bot has database access
3. Run `/admin sync-roles` manually
4. Check that roles are properly categorized with `/admin rebuild-role-categories`

### Foreign key violations still occurring

1. Check that `ROLE_SYNC_INTERVAL_MINUTES` is set appropriately
2. Manually run `/admin sync-roles`
3. Check logs to see which roles are failing
4. Verify the role exists in Discord

### Periodic sync not running

1. Check logs for "Periodic role sync task started" message
2. Verify `ROLE_SYNC_INTERVAL_MINUTES` is a positive integer
3. Check for errors in the RoleSyncCog initialization

## Database Schema

The role sync system uses these tables:

- **`roles`**: Stores Discord roles with metadata (role_id, role_name, category)
- **`assigned_roles`**: Current role assignments (user_id, role_id, assigned_at, assigned_by)
  - Foreign key constraint: `role_id` references `roles.role_id` with CASCADE delete
- **`role_history`**: Historical record of all role changes

## Architecture

```
Discord Events → RoleSyncCog → DatabaseService → PostgreSQL
                     ↓
              Periodic Task (every X minutes)
                     ↓
         Sync all categorized roles
                     ↓
              Notification on failure
```
