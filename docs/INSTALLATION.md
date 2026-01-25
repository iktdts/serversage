# Installation Guide

This guide covers the prerequisites, setup steps, and deployment options for ServerSage.

---

## Prerequisites

### Required

- **Python 3.8+** — The bot requires Python 3.8 or higher
- **Discord Bot Token** — Obtain from the [Discord Developer Portal](https://discord.com/developers/applications)
- **LLM API Key** — Either:
  - OpenAI API key (for GPT-4 or GPT-3.5-turbo)
  - Google AI API key (for Gemini models)
- **PostgreSQL Database** — For role tracking and user preferences

### Optional

- **Docker & Docker Compose** — Recommended for production deployment
- **Git** — For cloning the repository

### Discord Bot Requirements

Before running the bot, configure these in the Discord Developer Portal:

#### Privileged Gateway Intents

Enable these under **Application > Bot > Privileged Gateway Intents**:

- ✅ **Server Members Intent** — Required for detecting new members and accessing member lists
- ✅ **Message Content Intent** — Required for reading DM content during verification

#### Bot Permissions

When inviting the bot, include these permissions:

- **Manage Roles** — Assign/remove verification and skill roles
- **Send Messages** — Send DMs and channel messages
- **View Channels** — Access notification and welcome channels
- **Use Application Commands** — Enable slash commands
- **Read Message History** — Maintain DM conversation context
- **Embed Links** — Format rich messages

**Important:** The bot's role must be positioned **higher** in the server role hierarchy than any roles it needs to manage.

### Pre-Created Discord Roles

Create these roles in your Discord server before starting the bot:

- **Verified** role — Assigned upon successful verification
- **Unverified** role — Assigned to users awaiting verification
- **Verification In Progress** role — Temporary role during active verification
- **Admin** role(s) — For users who can execute admin commands
- **Suspicious** role (optional) — For flagged accounts

Skill, experience, and OS roles can be pre-created; the bot will categorize them automatically via LLM.

---

## Installation Methods

### Method 1: Local Development

1. **Clone the Repository**

   ```bash
   git clone <repository-url>
   cd serversage
   ```

2. **Create Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your configuration values. See [Configuration Reference](CONFIGURATION.md) for all options.

5. **Set Up Database**

   Ensure PostgreSQL is running and create a database:

   ```bash
   createdb serversage
   ```

   The bot will create tables automatically on first startup.

6. **Run the Bot**

   ```bash
   python main.py
   ```

### Method 2: Docker Deployment (Recommended for Production)

1. **Clone the Repository**

   ```bash
   git clone <repository-url>
   cd serversage
   ```

2. **Set Up Secrets**

   Create a `secrets/` directory with restricted permissions:

   ```bash
   mkdir -p secrets
   chmod 700 secrets
   ```

   Create secret files (ensure no trailing newlines):

   ```bash
   printf "your_discord_token" > secrets/discord_token.txt
   printf "your_llm_api_key" > secrets/llm_api_key.txt
   printf "your_db_password" > secrets/db_password.txt
   
   chmod 600 secrets/*.txt
   ```

3. **Configure Environment**

   Edit `docker-compose.yml` or create a `.env` file with non-secret configuration.

4. **Build and Start**

   ```bash
   docker-compose up -d --build
   ```

5. **View Logs**

   ```bash
   docker-compose logs -f
   ```

6. **Stop the Bot**

   ```bash
   docker-compose down
   ```

---

## Quick Start

Once installed and configured:

1. **First Startup** — The bot will:
   - Connect to Discord and sync slash commands
   - Initialize the database and create tables
   - Categorize server roles using the LLM (if no cached categorization exists)
   - Begin listening for events and commands

2. **Verify Role Categorization**
   - Check the logs for successful role categorization
   - The categorized roles are saved to `data/categorized_roles.json`

3. **Test Verification Flow**
   - Use `/admin verify-user @yourself` to test the DM verification
   - Or have a new member join to trigger automatic verification

4. **Sync Roles to Database**
   - Run `/admin sync-roles` to populate the database with role information

---

## Database Migrations

For existing installations, run migrations when updating:

```bash
cd migrations
./run_migrations.sh
```

Or with Docker:

```bash
docker-compose -f migrations/docker-compose.yml up --build
```

See [migrations/README_MIGRATIONS.md](../migrations/README_MIGRATIONS.md) for details.

---

## Troubleshooting

### Bot Not Responding to Commands

- Ensure slash commands are synced (check logs for "Synced X application commands")
- Verify the bot has proper permissions in your server
- Check that privileged intents are enabled in the Developer Portal

### Role Assignment Failures

- Confirm the bot's role is higher than roles it needs to assign
- Run `/admin sync-roles` to ensure roles exist in the database
- Check `NOTIFICATION_CHANNEL_ID` for error notifications

### LLM Connection Issues

- Verify `LLM_API_KEY` is correct
- Check `LLM_PROVIDER` matches your API key (openai vs gemini)
- For slow LLM providers, increase `LLM_HTTP_TIMEOUT_SECONDS`

### Database Connection Errors

- Confirm PostgreSQL is running and accessible
- Verify `DATABASE_*` environment variables are correct
- Check that the database user has proper permissions

---

## Next Steps

- [Configuration Reference](CONFIGURATION.md) — Detailed environment variable documentation
- [Architecture Overview](ARCHITECTURE.md) — Understanding the system design
