# Secrets Management Guide

## Overview

The bot supports loading secrets from files for enhanced security in production environments. This is especially important for Docker deployments and environments where secrets are managed by orchestration systems.

## Supported Secret Files

The following secrets can be loaded from files:

| Secret | Environment Variable | File Variable |
|--------|---------------------|---------------|
| Discord Bot Token | `DISCORD_BOT_TOKEN` | `DISCORD_BOT_TOKEN_FILE` |
| LLM API Key | `LLM_API_KEY` | `LLM_API_KEY_FILE` |
| Legacy LLM Token | `LLM_API_TOKEN` | `LLM_API_TOKEN_FILE` |
| Database Password | `DATABASE_PASSWORD` | `DATABASE_PASSWORD_FILE` |

## How It Works

### Priority Order

The bot uses this priority order for loading secrets:

1. **File Path** - If `*_FILE` variable is set and file exists, load from file
2. **Environment Variable** - If direct variable is set, use it
3. **Error** - If neither is set, warn or fail depending on the secret

### Example: Loading LLM API Key

```python
# Option 1: Direct environment variable
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx

# Option 2: File path (more secure)
LLM_API_KEY_FILE=/run/secrets/llm_api_key
```

The bot will:
1. Check if `LLM_API_KEY_FILE` is set and the file exists
2. If yes, read the API key from that file
3. If no, use the value from `LLM_API_KEY`
4. If neither is set, log a warning

## Setup Methods

### Method 1: Docker Secrets (Recommended for Production)

Docker Swarm and Docker Compose support native secrets management.

#### docker-compose.yml
```yaml
version: '3.8'

services:
  bot:
    image: serversage:latest
    secrets:
      - discord_bot_token
      - llm_api_key
      - database_password
    environment:
      # Point to secret file locations
      DISCORD_BOT_TOKEN_FILE: /run/secrets/discord_bot_token
      LLM_API_KEY_FILE: /run/secrets/llm_api_key
      DATABASE_PASSWORD_FILE: /run/secrets/database_password

      # Other non-secret configs
      LLM_PROVIDER: openai
      LLM_MODEL_NAME: gpt-4
      VERIFIED_ROLE_ID: 123456789012345678
      # ... other settings

secrets:
  discord_bot_token:
    file: ./secrets/discord_bot_token.txt
  llm_api_key:
    file: ./secrets/llm_api_key.txt
  database_password:
    file: ./secrets/database_password.txt
```

#### Creating Secret Files

```bash
# Create secrets directory
mkdir -p secrets
chmod 700 secrets

# Create secret files (one value per file, no newlines)
echo -n "your_discord_token" > secrets/discord_bot_token.txt
echo -n "sk-proj-xxxxxxxxxxxxx" > secrets/llm_api_key.txt
echo -n "your_db_password" > secrets/database_password.txt

# Secure the files
chmod 600 secrets/*.txt

# Add to .gitignore
echo "secrets/" >> .gitignore
```

### Method 2: Kubernetes Secrets

For Kubernetes deployments:

#### secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: serversage-secrets
type: Opaque
stringData:
  discord-bot-token: "your_discord_token"
  llm-api-key: "sk-proj-xxxxxxxxxxxxx"
  database-password: "your_db_password"
```

#### deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: serversage
spec:
  template:
    spec:
      containers:
      - name: bot
        image: serversage:latest
        env:
        - name: DISCORD_BOT_TOKEN_FILE
          value: /secrets/discord-bot-token
        - name: LLM_API_KEY_FILE
          value: /secrets/llm-api-key
        - name: DATABASE_PASSWORD_FILE
          value: /secrets/database-password
        - name: LLM_PROVIDER
          value: "openai"
        - name: LLM_MODEL_NAME
          value: "gpt-4"
        volumeMounts:
        - name: secrets
          mountPath: /secrets
          readOnly: true
      volumes:
      - name: secrets
        secret:
          secretName: serversage-secrets
```

Apply secrets:
```bash
kubectl apply -f secret.yaml
kubectl apply -f deployment.yaml
```

### Method 3: AWS Secrets Manager

For AWS deployments using ECS or EKS:

```bash
# Store secrets in AWS Secrets Manager
aws secretsmanager create-secret \
  --name serversage/discord-token \
  --secret-string "your_discord_token"

aws secretsmanager create-secret \
  --name serversage/llm-api-key \
  --secret-string "sk-proj-xxxxxxxxxxxxx"

aws secretsmanager create-secret \
  --name serversage/database-password \
  --secret-string "your_db_password"
```

Then retrieve and save to files in your deployment script:
```bash
#!/bin/bash
aws secretsmanager get-secret-value \
  --secret-id serversage/discord-token \
  --query SecretString --output text > /run/secrets/discord_bot_token

aws secretsmanager get-secret-value \
  --secret-id serversage/llm-api-key \
  --query SecretString --output text > /run/secrets/llm_api_key

aws secretsmanager get-secret-value \
  --secret-id serversage/database-password \
  --query SecretString --output text > /run/secrets/database_password

chmod 600 /run/secrets/*
```

### Method 4: Local Development

For local development, you can use either method:

#### Option A: Environment Variables in .env
```env
# .env file
DISCORD_BOT_TOKEN=your_token_here
LLM_API_KEY=sk-proj-xxxxxxxxxxxxx
DATABASE_PASSWORD=your_password
```

#### Option B: Secret Files
```bash
# Create local secrets directory
mkdir -p .secrets
chmod 700 .secrets

# Create secret files
echo -n "your_discord_token" > .secrets/discord_bot_token
echo -n "sk-proj-xxxxxxxxxxxxx" > .secrets/llm_api_key
echo -n "your_db_password" > .secrets/database_password

chmod 600 .secrets/*
```

Then in `.env`:
```env
# .env file
DISCORD_BOT_TOKEN_FILE=.secrets/discord_bot_token
LLM_API_KEY_FILE=.secrets/llm_api_key
DATABASE_PASSWORD_FILE=.secrets/database_password
```

**Important:** Add `.secrets/` to `.gitignore`:
```gitignore
# .gitignore
.secrets/
secrets/
*.key
*.secret
```

## Complete Configuration Example

### Production docker-compose.yml
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    secrets:
      - db_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
      POSTGRES_USER: serversage
      POSTGRES_DB: serversage
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - serversage-network

  bot:
    image: serversage:latest
    depends_on:
      - postgres
    secrets:
      - discord_bot_token
      - llm_api_key
      - db_password
    environment:
      # Secret file paths
      DISCORD_BOT_TOKEN_FILE: /run/secrets/discord_bot_token
      LLM_API_KEY_FILE: /run/secrets/llm_api_key
      DATABASE_PASSWORD_FILE: /run/secrets/db_password

      # LLM Configuration
      LLM_PROVIDER: openai
      LLM_MODEL_NAME: gpt-4
      LLM_HTTP_TIMEOUT_SECONDS: 120

      # Database Configuration
      DATABASE_HOST: postgres
      DATABASE_PORT: 5432
      DATABASE_NAME: serversage
      DATABASE_USER: serversage

      # Discord Configuration
      VERIFIED_ROLE_ID: 123456789012345678
      UNVERIFIED_ROLE_ID: 123456789012345679
      VERIFICATION_IN_PROGRESS_ROLE_ID: 123456789012345680
      ADMIN_ROLE_IDS: 111111111111111111,222222222222222222
      NOTIFICATION_CHANNEL_ID: 123456789012345681
      WELCOME_CHANNEL_ID: 123456789012345682

      # Bot Behavior
      VERIFICATION_RETRIES: 3
      REBUILD_ROLE_CATEGORIES_ON_STARTUP: false
      ROLE_SYNC_INTERVAL_MINUTES: 30
      LOG_LEVEL: INFO
    networks:
      - serversage-network
    restart: unless-stopped

secrets:
  discord_bot_token:
    file: ./secrets/discord_bot_token.txt
  llm_api_key:
    file: ./secrets/llm_api_key.txt
  db_password:
    file: ./secrets/database_password.txt

volumes:
  postgres_data:

networks:
  serversage-network:
    driver: bridge
```

### Setting up secrets for the above:
```bash
# Create secrets directory
mkdir -p secrets
chmod 700 secrets

# Create secret files (NO TRAILING NEWLINES!)
printf "your_discord_token" > secrets/discord_bot_token.txt
printf "sk-proj-xxxxxxxxxxxxx" > secrets/llm_api_key.txt
printf "your_database_password" > secrets/database_password.txt

# Secure the files
chmod 600 secrets/*.txt

# Verify (should show NO newlines)
od -c secrets/discord_bot_token.txt

# Start services
docker-compose up -d
```

## Security Best Practices

### 1. File Permissions

Always restrict secret file permissions:
```bash
# Owner read/write only
chmod 600 /path/to/secret

# Directory restricted to owner
chmod 700 /path/to/secrets/
```

### 2. Never Commit Secrets

Add to `.gitignore`:
```gitignore
# Secrets
.secrets/
secrets/
*.key
*.secret
*.pem
.env.production
.env.local
```

### 3. Use Different Secrets Per Environment

```bash
secrets/
├── dev/
│   ├── discord_bot_token.txt
│   ├── llm_api_key.txt
│   └── database_password.txt
├── staging/
│   ├── discord_bot_token.txt
│   ├── llm_api_key.txt
│   └── database_password.txt
└── production/
    ├── discord_bot_token.txt
    ├── llm_api_key.txt
    └── database_password.txt
```

### 4. Rotate Secrets Regularly

```bash
# Generate new API key with provider
# Update secret file
printf "new_api_key" > secrets/llm_api_key.txt

# Restart bot
docker-compose restart bot
```

### 5. Audit Secret Access

Check logs for secret loading:
```bash
docker-compose logs bot | grep "Loaded.*from file"
```

Expected output:
```
bot_1  | Loaded DISCORD_BOT_TOKEN from file.
bot_1  | Loaded LLM_API_KEY from file.
bot_1  | Loaded DATABASE_PASSWORD from file.
```

## Troubleshooting

### Secret File Not Found
```
Could not read secret from /run/secrets/llm_api_key: [Errno 2] No such file or directory
```

**Solution:**
- Verify the file path is correct
- Check file exists: `ls -la /run/secrets/`
- Verify Docker secrets are properly mounted

### Permission Denied
```
Could not read secret from /run/secrets/llm_api_key: [Errno 13] Permission denied
```

**Solution:**
```bash
chmod 600 /path/to/secret
chown botuser:botuser /path/to/secret
```

### Extra Newline in Secret
```
OpenAI API error: status=401 Invalid API key
```

**Cause:** Secret file has trailing newline

**Solution:** Use `printf` instead of `echo`:
```bash
# Wrong (adds newline)
echo "sk-proj-xxxxx" > secret.txt

# Correct (no newline)
printf "sk-proj-xxxxx" > secret.txt

# Or use echo -n
echo -n "sk-proj-xxxxx" > secret.txt
```

### Verify Secret Contents
```bash
# Check for newlines
od -c /run/secrets/llm_api_key

# Should not show \n at the end
```

## Migration from Environment Variables

### Step 1: Create Secret Files
```bash
mkdir -p secrets
chmod 700 secrets

# Extract from .env and create files
printf "$(grep DISCORD_BOT_TOKEN .env | cut -d= -f2)" > secrets/discord_bot_token.txt
printf "$(grep LLM_API_KEY .env | cut -d= -f2)" > secrets/llm_api_key.txt
printf "$(grep DATABASE_PASSWORD .env | cut -d= -f2)" > secrets/database_password.txt

chmod 600 secrets/*.txt
```

### Step 2: Update Configuration

Change from:
```env
DISCORD_BOT_TOKEN=your_token
LLM_API_KEY=sk-proj-xxxxx
DATABASE_PASSWORD=your_password
```

To:
```env
DISCORD_BOT_TOKEN_FILE=./secrets/discord_bot_token.txt
LLM_API_KEY_FILE=./secrets/llm_api_key.txt
DATABASE_PASSWORD_FILE=./secrets/database_password.txt
```

### Step 3: Test
```bash
# Test locally
python bot.py

# Check logs for confirmation
# Should see: "Loaded X from file."
```

### Step 4: Clean Up
```bash
# Remove secrets from .env
sed -i '/DISCORD_BOT_TOKEN=/d' .env
sed -i '/LLM_API_KEY=/d' .env
sed -i '/DATABASE_PASSWORD=/d' .env
```

## Summary

**Use Secret Files When:**
- ✅ Deploying to production
- ✅ Using Docker Swarm/Kubernetes
- ✅ Integrating with secrets managers (AWS, Vault, etc.)
- ✅ Need audit trails for secret access
- ✅ Want to rotate secrets without rebuilding containers

**Use Environment Variables When:**
- ✅ Local development
- ✅ Quick testing
- ✅ CI/CD pipelines with secret injection

**Never:**
- ❌ Commit secrets to version control
- ❌ Use weak file permissions
- ❌ Share secrets across environments
- ❌ Store secrets in container images
