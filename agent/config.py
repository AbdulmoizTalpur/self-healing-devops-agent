import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

class Config:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # New Multi-LLM configurations
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    # Determine default base URL based on provider if not explicitly specified
    _provider_lower = os.getenv("LLM_PROVIDER", "gemini").lower()
    if _provider_lower == "openrouter":
        _default_url = "https://openrouter.ai/api/v1"
    elif _provider_lower == "opencode":
        _default_url = "https://opencode.ai/zen/v1"
    else:
        _default_url = "https://api.openai.com/v1"
        
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", _default_url)

    try:
        CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))
    except ValueError:
        CONFIDENCE_THRESHOLD = 0.65

    @classmethod
    def validate(cls):
        """Validate critical environment variables."""
        errors = []
        if not cls.GITHUB_TOKEN:
            errors.append("GITHUB_TOKEN is not set.")
            
        provider = cls.LLM_PROVIDER.lower()
        if provider == "gemini":
            if not cls.GEMINI_API_KEY:
                errors.append("GEMINI_API_KEY is not set.")
        elif provider in ("openai", "openrouter", "opencode"):
            if not cls.OPENAI_API_KEY:
                errors.append(f"OPENAI_API_KEY is not set (required for LLM provider '{provider}').")
        else:
            errors.append(f"Unsupported LLM_PROVIDER: '{cls.LLM_PROVIDER}'. Supported: 'gemini', 'openai', 'openrouter', 'opencode'.")
            
        return errors
