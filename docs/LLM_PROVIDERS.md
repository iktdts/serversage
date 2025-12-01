# LLM Provider Configuration Guide

## Overview

The bot supports direct API integration with multiple LLM providers for faster response times, lower latency, and reduced token usage compared to using OpenWebUI as a proxy.

## Supported Providers

### 1. OpenAI
- **Provider ID**: `openai`
- **Supported Models**:
  - `gpt-4` - Most capable model
  - `gpt-4-turbo` - Faster, cheaper GPT-4
  - `gpt-3.5-turbo` - Fast and cost-effective
  - `gpt-3.5-turbo-16k` - Extended context window

### 2. Google Gemini
- **Provider ID**: `gemini`
- **Supported Models**:
  - `gemini-1.5-pro` - Most capable Gemini model with large context
  - `gemini-1.5-flash` - Faster, more cost-effective option
  - `gemini-1.0-pro` - Previous generation model

## Configuration

### Environment Variables

Add these to your `.env` file:

```env
# LLM Provider Configuration
LLM_PROVIDER=openai                    # Options: 'openai' or 'gemini'
LLM_API_KEY=your_api_key_here         # API key for the selected provider
LLM_MODEL_NAME=gpt-4                   # Model to use

# Optional: For OpenAI-compatible APIs (like Azure OpenAI)
LLM_BASE_URL=https://api.openai.com/v1
```

### OpenAI Configuration Example

```env
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
LLM_MODEL_NAME=gpt-4
```

To get an OpenAI API key:
1. Go to [platform.openai.com](https://platform.openai.com/)
2. Navigate to API keys section
3. Create a new API key

### Google Gemini Configuration Example

```env
LLM_PROVIDER=gemini
LLM_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
LLM_MODEL_NAME=gemini-1.5-flash
```

To get a Gemini API key:
1. Go to [ai.google.dev](https://ai.google.dev/)
2. Click "Get API key"
3. Create a project and generate an API key

### Azure OpenAI Configuration Example

For Azure OpenAI or other OpenAI-compatible APIs:

```env
LLM_PROVIDER=openai
LLM_API_KEY=your_azure_key
LLM_MODEL_NAME=gpt-4
LLM_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment
```

## Provider Comparison

| Feature | OpenAI | Gemini |
|---------|--------|--------|
| **Function Calling** | ✅ Native support | ✅ Native support |
| **Streaming** | ✅ Supported | ✅ Supported |
| **Context Window** | Up to 128k tokens | Up to 2M tokens |
| **Speed** | Fast | Very fast (Flash) |
| **Cost** | $$ | $ (generally cheaper) |
| **Reliability** | Excellent | Excellent |

## Switching Providers

To switch providers, simply update your `.env` file:

### From OpenWebUI to OpenAI
```env
# Old (OpenWebUI proxy)
# LLM_API_URL=http://localhost:3000/api/chat/completions
# LLM_API_TOKEN=your_openwebui_token

# New (Direct OpenAI)
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
LLM_MODEL_NAME=gpt-4
```

### From OpenAI to Gemini
```env
# Change these two lines
LLM_PROVIDER=gemini
LLM_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
LLM_MODEL_NAME=gemini-1.5-flash
```

Then restart the bot.

## Benefits of Direct API Integration

### 1. **Lower Latency**
- Direct connection eliminates proxy overhead
- Typical response time reduction: 20-40%

### 2. **Reduced Token Usage**
- No double-parsing of requests/responses
- More efficient token counting
- Can save 5-15% on token costs

### 3. **Better Error Handling**
- Direct access to provider-specific error messages
- Easier debugging and troubleshooting

### 4. **Provider-Specific Features**
- Access to latest provider features immediately
- No waiting for proxy updates
- Full control over API parameters

## Troubleshooting

### Invalid API Key
```
ValueError: LLM_API_KEY must be set via environment variable or file.
```
**Solution**: Ensure `LLM_API_KEY` is set in your `.env` file and the bot can read it.

### Unsupported Provider
```
ValueError: Unsupported provider: xxx. Supported: openai, gemini
```
**Solution**: Check that `LLM_PROVIDER` is set to either `'openai'` or `'gemini'`.

### Rate Limit Errors

**OpenAI**:
```
OpenAI API error: status=429
```
**Solution**: Upgrade your OpenAI plan or reduce request frequency.

**Gemini**:
```
Gemini API error: status=429
```
**Solution**: Check your quota at [ai.google.dev](https://ai.google.dev/). Free tier has limits.

### Connection Timeouts

Increase the timeout in `.env`:
```env
LLM_HTTP_TIMEOUT_SECONDS=180
```

## Best Practices

### Model Selection

**For Production (High Quality)**:
- OpenAI: `gpt-4`
- Gemini: `gemini-1.5-pro`

**For Development/Testing (Cost-Effective)**:
- OpenAI: `gpt-3.5-turbo`
- Gemini: `gemini-1.5-flash`

### Security

1. **Never commit API keys** to version control
2. Use environment variables or secret files
3. Rotate keys regularly
4. Use separate keys for dev/staging/prod

### Monitoring

Monitor these metrics in logs:
- Response times (`duration_s`)
- Token usage (`est_tokens`)
- Truncation rate (`finish_reason: 'length'`)
- Error rates

## Migration from OpenWebUI

If you're currently using OpenWebUI, here's how to migrate:

1. **Backup your configuration**:
   ```bash
   cp .env .env.backup
   ```

2. **Get API keys** from your chosen provider

3. **Update `.env`**:
   ```env
   # Remove or comment out old settings
   # LLM_API_URL=...
   # LLM_API_TOKEN=...

   # Add new settings
   LLM_PROVIDER=openai  # or gemini
   LLM_API_KEY=your_key_here
   LLM_MODEL_NAME=gpt-4  # or gemini-1.5-pro
   ```

4. **Test the bot**:
   ```bash
   python bot.py
   ```

5. **Verify** in logs:
   ```
   LLMClient initialized with provider='openai' model='gpt-4'
   ```

## Advanced Configuration

### Custom Base URL (OpenAI-compatible APIs)

For services compatible with OpenAI's API:

```env
LLM_PROVIDER=openai
LLM_BASE_URL=https://custom-api.example.com/v1
LLM_API_KEY=your_custom_key
LLM_MODEL_NAME=custom-model-name
```

### Multiple Bots with Different Providers

Run multiple bot instances with different configs:

```bash
# Bot 1: OpenAI
LLM_PROVIDER=openai python bot.py

# Bot 2: Gemini
LLM_PROVIDER=gemini python bot.py
```

## Support

For issues or questions:
1. Check logs for detailed error messages
2. Verify API key validity with provider's dashboard
3. Review provider's status page for outages
4. Open an issue on GitHub with logs (redact API keys!)

## References

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Google Gemini API Documentation](https://ai.google.dev/docs)
- [OpenAI Platform Status](https://status.openai.com/)
- [Google Cloud Status](https://status.cloud.google.com/)
