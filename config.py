# File: config.py

import logging
from typing import List, Optional
from pydantic import Field, PositiveInt, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

config_logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # Discord Bot Configuration
    DISCORD_BOT_TOKEN: Optional[str] = None
    DISCORD_BOT_TOKEN_FILE: Optional[str] = None

    # LLM API Configuration
    LLM_PROVIDER: str = "openai"  # Options: 'openai', 'gemini'
    LLM_API_KEY: Optional[str] = None
    LLM_API_KEY_FILE: Optional[str] = None
    LLM_MODEL_NAME: str = "gpt-4"  # OpenAI: 'gpt-4', 'gpt-3.5-turbo' | Gemini: 'gemini-1.5-pro', 'gemini-1.5-flash'
    LLM_BASE_URL: Optional[str] = None  # Optional custom base URL for OpenAI-compatible APIs

    # Legacy fields (kept for backward compatibility, will be removed in future)
    LLM_API_URL: Optional[HttpUrl] = None
    LLM_API_TOKEN: Optional[str] = None
    LLM_API_TOKEN_FILE: Optional[str] = None

    # Discord Role IDs
    VERIFIED_ROLE_ID: PositiveInt
    UNVERIFIED_ROLE_ID: PositiveInt
    VERIFICATION_IN_PROGRESS_ROLE_ID: PositiveInt
    
    ADMIN_ROLE_IDS_STR: str = Field("", alias="ADMIN_ROLE_IDS")

    # Discord Channel IDs
    NOTIFICATION_CHANNEL_ID: Optional[PositiveInt] = None
    WELCOME_CHANNEL_ID: Optional[PositiveInt] = None
    UNMAPPED_SKILLS_CHANNEL_ID: Optional[PositiveInt] = None
    LOBBY_CHANNEL_ID: Optional[PositiveInt] = None
    
    # Database Configuration
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: PositiveInt = 5432
    DATABASE_NAME: str = "serversage"
    DATABASE_USER: str = "serversage"
    DATABASE_PASSWORD: Optional[str] = None
    DATABASE_PASSWORD_FILE: Optional[str] = None
    
    # Bot Behavior Configuration
    VERIFICATION_RETRIES: PositiveInt = 3
    REBUILD_ROLE_CATEGORIES_ON_STARTUP: bool = False
    ROLE_SYNC_INTERVAL_MINUTES: PositiveInt = 30  # Sync roles every 30 minutes

    # LLM tuning: max tokens to request for generation and how much conversation history to keep
    LLM_MAX_RESPONSE_TOKENS: PositiveInt = 4096
    LLM_MAX_HISTORY_MESSAGES: PositiveInt = 8
    # HTTP timeout (seconds) for LLM API calls (can be increased for slower local LLMs)
    LLM_HTTP_TIMEOUT_SECONDS: PositiveInt = 120

    # Suspicious account / moderation settings
    SUSPICIOUS_ROLE_ID: Optional[PositiveInt] = 1426422431886741545
    SUSPICIOUS_CHECK_INTERVAL_HOURS: PositiveInt = 24
    SUSPICIOUS_ROLE_RETENTION_DAYS: PositiveInt = 7
    LLM_SUMMARY_MAX_CHARS: PositiveInt = 1800

    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    # File Paths
    PROMPT_PATH_ROLE_CATEGORIZATION_SYSTEM: str = "prompts/role_categorization/system.txt"
    PROMPT_PATH_USER_VERIFICATION_SYSTEM_TEMPLATE: str = "prompts/user_verification/system_template.txt"
    PROMPT_PATH_CHANNEL_WELCOME_SYSTEM_TEMPLATE: str = "prompts/welcome_message/system_template.txt"
    PROMPT_PATH_NEW_USER_SUMMARY_SYSTEM_TEMPLATE: str = "prompts/new_user_summary/system_template.txt"
    PROMPT_PATH_SUSPICIOUS_ANALYSIS_SYSTEM_TEMPLATE: str = "prompts/suspicious_analysis/system_template.txt"
    CATEGORIZED_ROLES_FILE: str = "data/categorized_roles.json"
    USER_VERIFICATION_SCHEMA_PATH: str = "llm_integration/schemas/user_verification.json"
    ROLE_CATEGORIZATION_SCHEMA_PATH: str = "llm_integration/schemas/role_categorization.json"
    # Role hierarchy boundary (optional). If set, only roles below this role will be considered for
    # automatic categorization. Specify the numeric role ID via env. Name-based resolution is not used.
    HIERARCHY_BOUNDARY_ROLE_ID: Optional[PositiveInt] = None

    PARSED_ADMIN_ROLE_IDS: List[int] = []

    @property
    def DATABASE_URL(self) -> str:
        """Construct the PostgreSQL database URL for async connections."""
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    @model_validator(mode='after')
    def load_secrets_from_files(self) -> 'Settings':
        """Load secrets from files if the corresponding _FILE env var is set."""
        if self.DISCORD_BOT_TOKEN_FILE and os.path.exists(self.DISCORD_BOT_TOKEN_FILE):
            try:
                with open(self.DISCORD_BOT_TOKEN_FILE, 'r') as f:
                    self.DISCORD_BOT_TOKEN = f.read().strip()
                config_logger.info("Loaded DISCORD_BOT_TOKEN from file.")
            except Exception as e:
                config_logger.error(f"Could not read secret from {self.DISCORD_BOT_TOKEN_FILE}: {e}")

        # Load LLM_API_KEY from file (new provider-based approach)
        if self.LLM_API_KEY_FILE and os.path.exists(self.LLM_API_KEY_FILE):
            try:
                with open(self.LLM_API_KEY_FILE, 'r') as f:
                    self.LLM_API_KEY = f.read().strip()
                config_logger.info("Loaded LLM_API_KEY from file.")
            except Exception as e:
                config_logger.error(f"Could not read secret from {self.LLM_API_KEY_FILE}: {e}")

        # Legacy: Load LLM_API_TOKEN from file (backward compatibility)
        if self.LLM_API_TOKEN_FILE and os.path.exists(self.LLM_API_TOKEN_FILE):
            try:
                with open(self.LLM_API_TOKEN_FILE, 'r') as f:
                    self.LLM_API_TOKEN = f.read().strip()
                config_logger.info("Loaded LLM_API_TOKEN from file (legacy).")
                # If new API key not set, use legacy token
                if not self.LLM_API_KEY:
                    self.LLM_API_KEY = self.LLM_API_TOKEN
            except Exception as e:
                config_logger.error(f"Could not read secret from {self.LLM_API_TOKEN_FILE}: {e}")

        # Backward compatibility: use legacy LLM_API_TOKEN if LLM_API_KEY not set
        if not self.LLM_API_KEY and self.LLM_API_TOKEN:
            self.LLM_API_KEY = self.LLM_API_TOKEN
            config_logger.info("Using legacy LLM_API_TOKEN as LLM_API_KEY for backward compatibility.")

        if self.DATABASE_PASSWORD_FILE and os.path.exists(self.DATABASE_PASSWORD_FILE):
            try:
                with open(self.DATABASE_PASSWORD_FILE, 'r') as f:
                    self.DATABASE_PASSWORD = f.read().strip()
                config_logger.info("Loaded DATABASE_PASSWORD from file.")
            except Exception as e:
                config_logger.error(f"Could not read secret from {self.DATABASE_PASSWORD_FILE}: {e}")

        if not self.DISCORD_BOT_TOKEN:
            raise ValueError("DISCORD_BOT_TOKEN must be set via environment variable or file.")

        if not self.LLM_API_KEY:
            config_logger.warning("LLM_API_KEY is not set. LLM functionality will not work.")
            # Don't raise error to allow partial startup for debugging

        if not self.DATABASE_PASSWORD:
            config_logger.warning("DATABASE_PASSWORD is not set. Database connection may fail.")

        # Validate provider
        if self.LLM_PROVIDER.lower() not in ['openai', 'gemini']:
            raise ValueError(f"Invalid LLM_PROVIDER: {self.LLM_PROVIDER}. Must be 'openai' or 'gemini'.")

        return self

    @property
    def ADMIN_ROLES_AS_INT_LIST(self) -> List[int]:
        if not self.ADMIN_ROLE_IDS_STR:
            return []
        try:
            return [int(role_id.strip()) for role_id in self.ADMIN_ROLE_IDS_STR.split(',') if role_id.strip().isdigit()]
        except ValueError as e:
            config_logger.error(f"Invalid ADMIN_ROLE_IDS format: '{self.ADMIN_ROLE_IDS_STR}'. Must be comma-separated integers. Error: {e}")
            return []

try:
    settings = Settings()
    settings.PARSED_ADMIN_ROLE_IDS = settings.ADMIN_ROLES_AS_INT_LIST
except Exception as e:
    config_logger.critical(f"CRITICAL: Failed to load application settings. Error: {e}", exc_info=True)
    print(f"CRITICAL: Failed to load application settings. Error: {e}\nCheck your .env file and configurations.")
    raise SystemExit(f"Configuration load failed: {e}")
