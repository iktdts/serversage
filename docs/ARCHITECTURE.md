# Architecture Overview

This document describes the system architecture, components, and data flow of ServerSage.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Discord Platform                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Member Join │  │   Slash      │  │  Role Events │  │     DMs      │     │
│  │    Events    │  │  Commands    │  │              │  │              │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VerificationBot (bot.py)                          │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          Cogs (Commands & Events)                     │   │
│  │  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐            │   │
│  │  │ AdminCommands  │ │ UserCommands   │ │ EventListeners │            │   │
│  │  │     Cog        │ │     Cog        │ │     Cog        │            │   │
│  │  └────────┬───────┘ └────────┬───────┘ └────────┬───────┘            │   │
│  └───────────┼──────────────────┼──────────────────┼────────────────────┘   │
│              │                  │                  │                        │
│              ▼                  ▼                  ▼                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                             Services                                  │   │
│  │  ┌────────────────────┐  ┌────────────────────┐  ┌───────────────┐   │   │
│  │  │ VerificationFlow   │  │ SuspiciousAccount  │  │  Database     │   │   │
│  │  │     Service        │  │     Service        │  │   Service     │   │   │
│  │  └─────────┬──────────┘  └─────────┬──────────┘  └───────┬───────┘   │   │
│  └────────────┼───────────────────────┼─────────────────────┼───────────┘   │
│               │                       │                     │               │
│               ▼                       ▼                     ▼               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                           LLM Integration                             │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐          │   │
│  │  │   LLMClient    │──│ OpenAIProvider │  │ GeminiProvider │          │   │
│  │  │                │  └────────────────┘  └────────────────┘          │   │
│  │  └────────────────┘                                                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
            │  PostgreSQL  │    │  OpenAI API  │    │  Gemini API  │
            │   Database   │    │              │    │              │
            └──────────────┘    └──────────────┘    └──────────────┘
```

---

## Project Structure

```
serversage/
├── main.py                 # Entry point, logging setup, bot startup
├── bot.py                  # VerificationBot class, setup_hook, lifecycle
├── config.py               # Pydantic Settings, environment configuration
│
├── cogs/                   # Discord command and event handlers
│   ├── admin_commands_cog.py    # Admin slash commands
│   ├── user_commands_cog.py     # User slash commands
│   ├── event_listeners_cog.py   # Event handlers, role categorization
│   └── role_sync_cog.py         # Background role synchronization
│
├── services/               # Business logic layer
│   ├── verification_flow_service.py    # Verification state machine
│   ├── suspicious_account_service.py   # Threat detection service
│   └── database_service.py             # Database operations
│
├── llm_integration/        # LLM abstraction layer
│   ├── llm_client.py           # High-level LLM interface
│   ├── providers/              # Provider implementations
│   │   ├── base.py             # BaseLLMProvider abstract class
│   │   ├── openai_provider.py  # OpenAI API client
│   │   └── gemini_provider.py  # Gemini API client
│   └── schemas/                # Function calling JSON schemas
│       ├── user_verification.json
│       ├── role_categorization.json
│       └── suspicious_classification.json
│
├── database/               # Database layer
│   ├── __init__.py             # Engine initialization, table creation
│   └── models.py               # SQLAlchemy ORM models
│
├── prompts/                # LLM prompt templates
│   ├── role_categorization/
│   ├── user_verification/
│   ├── welcome_message/
│   ├── new_user_summary/
│   └── suspicious_analysis/
│
├── utils/                  # Utilities
│   ├── logging_setup.py        # Logging configuration
│   └── i18n.py                 # Internationalization helpers
│
├── data/                   # Runtime data storage
│   └── categorized_roles.json  # Cached role categorization
│
├── migrations/             # Database migration scripts
└── docs/                   # Documentation
```

---

## Core Components

### VerificationBot (bot.py)

The main bot class extending `commands.Bot`:

- **Initialization**: Creates shared HTTP session, initializes LLM client and services
- **setup_hook()**: Async initialization that runs before the bot is ready
  - Initializes database connection
  - Creates `LLMClient` with configured provider
  - Creates `VerificationFlowService` and `SuspiciousAccountService`
  - Auto-loads all cogs from `cogs/` directory
- **Lifecycle**: Manages graceful shutdown and resource cleanup

### Cogs

Modular command and event handlers following discord.py conventions:

#### AdminCommandsCog
- Admin-only slash commands under `/admin` group
- Role-based access control via `check_admin_roles()`
- Commands: verify-user, initiate-verification-batch, reset-stale-verifications, rebuild-role-categories, sync-roles

#### UserCommandsCog
- User-facing slash commands
- `/assign-roles`: Self-service verification with interactive role selector for verified users

#### EventListenersCog
- Discord event handlers: `on_member_join`, `on_guild_role_create/update/delete`
- Role categorization logic (initial and rebuild)
- Loads/saves categorized roles from/to JSON file

#### RoleSyncCog
- Background task for periodic role synchronization
- Configurable interval via `ROLE_SYNC_INTERVAL_MINUTES`

### Services

Business logic isolated from Discord-specific code:

#### VerificationFlowService
- Manages verification state machine
- Tracks active verifications in `active_verifications` dict (keyed by member ID)
- Handles DM conversation flow with LLM
- Processes role proposals and confirmations
- Assigns roles and updates database

**State Flow:**
```
New Member → DM Sent → Awaiting Response → LLM Processing → 
Role Proposal → User Confirmation → Role Assignment → Complete
```

#### SuspiciousAccountService
- LLM-based behavioral analysis for threat detection
- Periodic cleanup task for suspicious role retention
- Admin notification for flagged accounts

#### DatabaseService
- Async database operations
- Role tracking and history
- User preference storage

### LLM Integration

#### LLMClient
High-level interface for LLM operations:

- `categorize_server_roles()`: Taxonomy generation from server roles
- `get_verification_guidance()`: Verification conversation with function calling
- `generate_welcome_message()`: Welcome embed content generation
- `generate_new_user_summary()`: User summary for admins
- `classify_user_for_suspicion()`: Threat detection analysis

**Key Features:**
- Provider-agnostic interface
- Function calling support with JSON schema validation
- Response parsing and fallback handling
- Metrics tracking (calls, tokens, truncation)

#### Providers

**BaseLLMProvider** (Abstract):
- Defines interface: `request()`, `get_provider_name()`, `supports_function_calling()`

**OpenAIProvider**:
- Direct REST API calls to OpenAI Chat Completions endpoint
- Supports custom base URLs for OpenAI-compatible APIs
- Retry logic for transient failures

**GeminiProvider**:
- Native Gemini API integration
- Automatic format conversion (OpenAI format ↔ Gemini format)
- Function calling translation

---

## Data Flow

### Verification Flow

```
1. User joins / uses /assign-roles / admin triggers
              │
              ▼
2. VerificationFlowService.start_verification_process()
   - Assigns "verification-in-progress" role
   - Sends initial DM
              │
              ▼
3. DM Conversation Loop
   - User sends message
   - LLMClient.get_verification_guidance() called
   - LLM returns structured response (function calling)
   - Bot sends response to user
              │
              ▼
4. Role Proposal
   - LLM proposes roles with classification
   - User confirms or provides more info
              │
              ▼
5. Role Assignment
   - DatabaseService records assignment
   - Discord roles updated
   - "verified" role assigned
   - "verification-in-progress" role removed
```

### Role Categorization Flow

```
1. Startup / Admin command / Force rebuild
              │
              ▼
2. EventListenersCog.perform_role_categorization()
   - Fetches all guild roles
   - Filters by hierarchy boundary (optional)
   - Excludes system/managed roles
              │
              ▼
3. LLMClient.categorize_server_roles()
   - Sends role list with categorization prompt
   - Function calling: categorize_server_roles
   - Returns category → role names mapping
              │
              ▼
4. Post-processing
   - Maps role names to IDs
   - Assigns uncategorized roles to "Other"
   - Saves to data/categorized_roles.json
              │
              ▼
5. Updates bot.categorized_server_roles and bot.server_roles_map
```

---

## Database Schema

```
┌────────────────────┐       ┌────────────────────┐
│       roles        │       │   assigned_roles   │
├────────────────────┤       ├────────────────────┤
│ role_id (PK)       │◄──────│ role_id (FK)       │
│ role_name          │       │ user_id            │
│ category           │       │ assigned_at        │
│ created_at         │       │ assigned_by        │
│ updated_at         │       └────────────────────┘
└────────────────────┘
                             ┌────────────────────┐
┌────────────────────┐       │   role_history     │
│  unmapped_skills   │       ├────────────────────┤
├────────────────────┤       │ user_id            │
│ user_id            │       │ role_name          │
│ user_name          │       │ action             │
│ skill_name         │       │ triggered_by       │
│ suggested_category │       │ timestamp          │
│ mentioned_at       │       └────────────────────┘
│ source             │
└────────────────────┘       ┌────────────────────┐
                             │  user_preferences  │
                             ├────────────────────┤
                             │ user_id (PK)       │
                             │ preferred_locale   │
                             │ updated_at         │
                             └────────────────────┘
```

---

## Extension Points

### Adding a New LLM Provider

1. Create a new file in `llm_integration/providers/`
2. Extend `BaseLLMProvider`
3. Implement `request()`, `get_provider_name()`
4. Handle format conversion if needed
5. Register in `LLMClient.__init__()`

### Adding New Classification Categories

1. Update `llm_integration/schemas/user_verification.json`
2. Modify prompts in `prompts/user_verification/system_template.txt`
3. Update role categorization prompt in `prompts/role_categorization/system.txt`

### Adding New Commands

1. Create a new cog file in `cogs/` with `*_cog.py` naming
2. Implement `async def setup(bot)` function
3. The cog will be auto-loaded by `setup_hook()`

---

## Security Considerations

- **Secrets**: Use `*_FILE` environment variables in production
- **Permissions**: Bot role must be higher than managed roles
- **Access Control**: Admin commands require configured admin roles
- **Input Validation**: Pydantic validates all configuration
- **Database**: Foreign key constraints ensure data integrity
