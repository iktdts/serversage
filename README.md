# ServerSage

**An AI-Powered Discord Verification Bot with Conversational Intelligence**

ServerSage is an intelligent Discord bot that leverages **Large Language Models (LLMs)** to automate user verification through natural language conversations. It demonstrates advanced AI/ML integration patterns including multi-provider LLM orchestration, function calling (tool use), natural language understanding for classification, and real-time threat detection.

---

## AI & Machine Learning Capabilities

### 🧠 Multi-Provider LLM Integration

ServerSage implements a **pluggable provider architecture** for seamless integration with multiple LLM providers:

- **OpenAI GPT-4 / GPT-3.5-turbo** — Direct REST API integration with the OpenAI Chat Completions endpoint
- **Google Gemini** (gemini-1.5-pro, gemini-1.5-flash) — Native Gemini API integration with automatic format conversion
- **OpenAI-Compatible APIs** — Support for Azure OpenAI, local LLM servers, and any OpenAI-compatible endpoint via configurable base URL

The provider abstraction (`BaseLLMProvider`) enables runtime provider switching without code changes, demonstrating **strategy pattern** implementation for AI service integration.

### 🔧 Function Calling / Tool Use

The bot implements **structured output generation** through LLM function calling:

| Function | Purpose | Output Schema |
|----------|---------|---------------|
| `propose_user_roles` | Multi-category skill classification with confirmation flow | Classification dict, user message, completion status, confirmation state |
| `categorize_server_roles` | Automated role taxonomy generation from server roles | Category-to-role-names mapping |
| `classify_user` | Suspicious account detection with evidence extraction | Boolean flag, reason string, classification tags |

Function definitions use **JSON Schema** for type-safe structured responses, with automatic fallback handling when function calls fail or return malformed data.

### 🎯 Natural Language Understanding for Classification

ServerSage performs **multi-label, multi-category classification** from unstructured user input:

- **Entity Recognition** — Extracts programming languages, frameworks, tools, and experience levels from conversational text
- **Fuzzy Skill Matching** — Maps user-mentioned skills to available Discord roles using semantic understanding
- **Multi-Turn Context** — Maintains conversation history for coherent dialogue and progressive information gathering
- **Unmapped Skill Detection** — Identifies and reports skills mentioned by users that don't have corresponding server roles

**Classification Categories:**
- Programming Languages (Python, JavaScript, Rust, etc.)
- Experience Levels (Beginner, Intermediate, Senior, Expert)
- Operating Systems (Linux, Windows, macOS)
- Tools (Docker, Git, VS Code, etc.)
- Frameworks (React, Django, FastAPI, etc.)

### 🛡️ AI-Powered Threat Detection

The **Suspicious Account Service** uses LLM-based behavioral analysis to identify potentially malicious accounts:

- **Pattern Recognition** — Analyzes message patterns for spam, phishing, bot-like behavior, and scam indicators
- **Evidence Extraction** — Generates human-readable explanations citing specific evidence from user messages
- **Classification Tags** — Assigns tags: `spam`, `phishing`, `scam`, `bot`, `automated`, `gibberish`, `harassment`
- **Automated Response** — Applies suspicious role, notifies admins, and manages automatic cleanup after retention period

The system uses **zero-shot classification** with carefully engineered prompts to avoid false positives while catching genuine threats.

### 🌍 Intelligent Localization (i18n)

ServerSage implements **language-aware AI responses**:

- **Locale Detection** — Extracts user locale from Discord interaction metadata
- **Preference Persistence** — Stores language preferences in PostgreSQL for consistent experience
- **Dynamic Prompt Localization** — Instructs the LLM to respond in the user's preferred language
- **Fallback Handling** — Graceful degradation to English/Spanish when locale-specific responses fail

### 📝 Natural Language Generation

The bot generates contextual, human-like messages for:

- **Welcome Messages** — LLM-generated welcome embeds for new members with customizable temperature
- **Verification Dialogue** — Dynamic conversational responses that guide users through the verification process
- **User Summaries** — AI-generated summaries of verification conversations for admin review
- **Role Proposals** — Formatted Markdown messages presenting proposed role assignments

### 🔄 Dynamic Role Taxonomy

The **automated role categorization** system uses LLM to:

1. Fetch all Discord server roles
2. Filter by configurable hierarchy boundary
3. Send role list to LLM with categorization prompt
4. Parse structured function call response
5. Cache results for efficient runtime access
6. Support on-demand recategorization via admin command

---

## Technical Highlights

### Prompt Engineering

External prompt templates enable rapid iteration without code changes:

```
prompts/
├── role_categorization/system.txt      # Role taxonomy prompt
├── user_verification/system_template.txt  # Verification conversation
├── welcome_message/system_template.txt    # Welcome embed generation
├── new_user_summary/system_template.txt   # User summary for admins
└── suspicious_analysis/system_template.txt # Threat detection
```

Templates use Python's `string.Template` for safe substitution with variables like `${available_roles_text_list}`, `${preferred_locale}`, and `${conversation_history}`.

### Metrics & Observability

Built-in LLM usage tracking:

- Call count and estimated token consumption
- Response truncation detection (finish_reason: length)
- Request duration measurement
- Character count per request

### Resilience Patterns

- **Retry Logic** — Automatic retries for transient LLM API failures
- **Partial Assignment** — Assigns valid roles even when some fail
- **Graceful Degradation** — Falls back to hardcoded messages when LLM unavailable
- **Timeout Configuration** — Adjustable HTTP timeouts for slow LLM providers

---

## Core Features

- **Automated Verification** — New members receive DM-based verification powered by conversational AI
- **Admin Commands** — Batch verification, stale session cleanup, role recategorization
- **Self-Service** — Users can initiate or update their roles via `/assign-roles`
- **Database Tracking** — PostgreSQL with SQLAlchemy async for role history and analytics
- **Real-Time Sync** — Discord event-driven role synchronization with periodic background sync
- **Docker Support** — Production-ready containerization with docker-compose

---

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/INSTALLATION.md) | Prerequisites, setup steps, and deployment options |
| [Configuration Reference](docs/CONFIGURATION.md) | Environment variables and settings |
| [Architecture Overview](docs/ARCHITECTURE.md) | System design, components, and data flow |

---

## Technology Stack

- **Python 3.8+** with async/await patterns
- **discord.py** for Discord API integration
- **httpx** for async HTTP client
- **Pydantic** for configuration validation
- **SQLAlchemy 2.0** with asyncpg for PostgreSQL
- **Docker** for containerized deployment

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
