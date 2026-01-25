# Configuration Reference

ServerSage uses environment variables for configuration. These can be set via a `.env` file, environment variables, or secret files (for sensitive values).

---

## Configuration Methods

### Environment Variables

Set variables directly in your environment or in a `.env` file in the project root.

### Secret Files

For sensitive values in production, use the `*_FILE` suffix to read from files:

```bash
# Instead of:
DISCORD_BOT_TOKEN=your_token_here

# Use:
DISCORD_BOT_TOKEN_FILE=/run/secrets/discord_token
```

The bot automatically reads the file content and strips whitespace.

**Supported secret files:**
- `DISCORD_BOT_TOKEN_FILE`
- `LLM_API_KEY_FILE`
- `LLM_API_TOKEN_FILE` (legacy)
- `DATABASE_PASSWORD_FILE`

---

## Environment Variables

### Discord Bot Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token | ✅ Yes | — |
| `DISCORD_BOT_TOKEN_FILE` | Path to file containing bot token | No | — |

### LLM Provider Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LLM_PROVIDER` | LLM provider: `openai` or `gemini` | No | `openai` |
| `LLM_API_KEY` | API key for the selected LLM provider | ✅ Yes | — |
| `LLM_API_KEY_FILE` | Path to file containing API key | No | — |
| `LLM_MODEL_NAME` | Model identifier | No | `gpt-4` |
| `LLM_BASE_URL` | Custom base URL for OpenAI-compatible APIs | No | `https://api.openai.com/v1` |

**Model Options:**

| Provider | Models |
|----------|--------|
| OpenAI | `gpt-4`, `gpt-3.5-turbo`, `gpt-4-turbo` |
| Gemini | `gemini-1.5-pro`, `gemini-1.5-flash` |

### Discord Role IDs

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `VERIFIED_ROLE_ID` | Role ID for verified users | ✅ Yes | — |
| `UNVERIFIED_ROLE_ID` | Role ID for unverified users | ✅ Yes | — |
| `VERIFICATION_IN_PROGRESS_ROLE_ID` | Temporary role during verification | ✅ Yes | — |
| `ADMIN_ROLE_IDS` | Comma-separated list of admin role IDs | ✅ Yes | — |
| `SUSPICIOUS_ROLE_ID` | Role for flagged suspicious accounts | No | — |
| `HIERARCHY_BOUNDARY_ROLE_ID` | Only categorize roles below this role | No | — |

**Example:**
```env
VERIFIED_ROLE_ID=1234567890123456789
UNVERIFIED_ROLE_ID=1234567890123456790
VERIFICATION_IN_PROGRESS_ROLE_ID=1234567890123456791
ADMIN_ROLE_IDS=1111111111111111111,2222222222222222222
```

### Discord Channel IDs

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `NOTIFICATION_CHANNEL_ID` | Channel for admin notifications | No | — |
| `WELCOME_CHANNEL_ID` | Channel for welcome messages | No | — |
| `UNMAPPED_SKILLS_CHANNEL_ID` | Channel for unmapped skill reports | No | — |
| `LOBBY_CHANNEL_ID` | Lobby/landing channel | No | — |

### Database Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_HOST` | PostgreSQL host | No | `localhost` |
| `DATABASE_PORT` | PostgreSQL port | No | `5432` |
| `DATABASE_NAME` | Database name | No | `serversage` |
| `DATABASE_USER` | Database user | No | `serversage` |
| `DATABASE_PASSWORD` | Database password | ✅ Yes | — |
| `DATABASE_PASSWORD_FILE` | Path to file containing password | No | — |

### Bot Behavior

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `VERIFICATION_RETRIES` | Max retry attempts per verification session | No | `3` |
| `REBUILD_ROLE_CATEGORIES_ON_STARTUP` | Force role recategorization on startup | No | `false` |
| `ROLE_SYNC_INTERVAL_MINUTES` | Background role sync interval | No | `30` |

### LLM Tuning

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LLM_MAX_RESPONSE_TOKENS` | Max tokens for LLM responses | No | `4096` |
| `LLM_MAX_HISTORY_MESSAGES` | Max conversation history messages | No | `8` |
| `LLM_HTTP_TIMEOUT_SECONDS` | HTTP timeout for LLM calls | No | `120` |
| `DEFAULT_MAX_TOKENS` | Global default max tokens | No | `6144` |

### Suspicious Account Detection

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SUSPICIOUS_ROLE_ID` | Role for suspicious accounts | No | — |
| `SUSPICIOUS_CHECK_INTERVAL_HOURS` | Cleanup task interval | No | `24` |
| `SUSPICIOUS_ROLE_RETENTION_DAYS` | Days before auto-removing suspicious role | No | `7` |
| `LLM_SUMMARY_MAX_CHARS` | Max chars for user summaries | No | `1800` |

### Welcome Message Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `WELCOME_TEMPERATURE` | LLM temperature for welcome messages | No | `0.7` |
| `WELCOME_HARDCODE` | Use static message instead of LLM | No | `false` |
| `WELCOME_HARDCODE_MESSAGE` | Static fallback welcome message | No | — |
| `WELCOME_MAX_PROMPT_CHARS` | Max chars in welcome prompt | No | `800` |
| `WELCOME_MAX_RESPONSE_TOKENS` | Max tokens for welcome response | No | `1024` |

### Logging

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LOG_LEVEL` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` | No | `INFO` |

### File Paths

| Variable | Description | Default |
|----------|-------------|---------|
| `PROMPT_PATH_ROLE_CATEGORIZATION_SYSTEM` | Role categorization prompt | `prompts/role_categorization/system.txt` |
| `PROMPT_PATH_USER_VERIFICATION_SYSTEM_TEMPLATE` | Verification prompt template | `prompts/user_verification/system_template.txt` |
| `PROMPT_PATH_CHANNEL_WELCOME_SYSTEM_TEMPLATE` | Welcome message prompt | `prompts/welcome_message/system_template.txt` |
| `PROMPT_PATH_NEW_USER_SUMMARY_SYSTEM_TEMPLATE` | User summary prompt | `prompts/new_user_summary/system_template.txt` |
| `PROMPT_PATH_SUSPICIOUS_ANALYSIS_SYSTEM_TEMPLATE` | Suspicious analysis prompt | `prompts/suspicious_analysis/system_template.txt` |
| `CATEGORIZED_ROLES_FILE` | Cached role categorization | `data/categorized_roles.json` |
| `USER_VERIFICATION_SCHEMA_PATH` | Verification function schema | `llm_integration/schemas/user_verification.json` |
| `ROLE_CATEGORIZATION_SCHEMA_PATH` | Categorization function schema | `llm_integration/schemas/role_categorization.json` |

---

## Example Configurations

### Minimal Configuration

```env
# Required
DISCORD_BOT_TOKEN=your_discord_token
LLM_API_KEY=sk-proj-your_openai_key
DATABASE_PASSWORD=your_db_password

# Role IDs
VERIFIED_ROLE_ID=1234567890123456789
UNVERIFIED_ROLE_ID=1234567890123456790
VERIFICATION_IN_PROGRESS_ROLE_ID=1234567890123456791
ADMIN_ROLE_IDS=1111111111111111111
```

### Production Configuration with Gemini

```env
# Secrets (use files in production)
DISCORD_BOT_TOKEN_FILE=/run/secrets/discord_token
LLM_API_KEY_FILE=/run/secrets/llm_api_key
DATABASE_PASSWORD_FILE=/run/secrets/db_password

# LLM Provider
LLM_PROVIDER=gemini
LLM_MODEL_NAME=gemini-1.5-flash

# Role IDs
VERIFIED_ROLE_ID=1234567890123456789
UNVERIFIED_ROLE_ID=1234567890123456790
VERIFICATION_IN_PROGRESS_ROLE_ID=1234567890123456791
ADMIN_ROLE_IDS=1111111111111111111,2222222222222222222
SUSPICIOUS_ROLE_ID=3333333333333333333

# Channels
NOTIFICATION_CHANNEL_ID=4444444444444444444
WELCOME_CHANNEL_ID=5555555555555555555

# Database
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_NAME=serversage
DATABASE_USER=serversage

# Tuning
VERIFICATION_RETRIES=3
ROLE_SYNC_INTERVAL_MINUTES=30
LLM_HTTP_TIMEOUT_SECONDS=120
LOG_LEVEL=INFO
```

### Development Configuration

```env
DISCORD_BOT_TOKEN=your_token
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-your_key
LLM_MODEL_NAME=gpt-3.5-turbo

VERIFIED_ROLE_ID=1234567890123456789
UNVERIFIED_ROLE_ID=1234567890123456790
VERIFICATION_IN_PROGRESS_ROLE_ID=1234567890123456791
ADMIN_ROLE_IDS=1111111111111111111

DATABASE_HOST=localhost
DATABASE_PASSWORD=devpassword

REBUILD_ROLE_CATEGORIES_ON_STARTUP=true
LOG_LEVEL=DEBUG
```

---

## Notes

### Token Limits

Increasing `DEFAULT_MAX_TOKENS` or per-call limits can reduce truncation but:
- Uses more compute/API credits
- May exceed model limits
- Consider trimming prompts instead

### Hierarchy Boundary

Setting `HIERARCHY_BOUNDARY_ROLE_ID` limits which roles the bot categorizes:
- Only roles **below** this role in the hierarchy are considered
- Useful for excluding admin/system roles from categorization
- If the boundary role is not found, categorization is aborted for safety

### Legacy Compatibility

The following legacy variables are still supported for backward compatibility:
- `LLM_API_TOKEN` → Maps to `LLM_API_KEY`
- `LLM_API_TOKEN_FILE` → Maps to `LLM_API_KEY_FILE`
- `LLM_API_URL` → Deprecated, use `LLM_BASE_URL`
