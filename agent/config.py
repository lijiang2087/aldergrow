"""Load settings from environment. Uses python-dotenv so .env is loaded when present."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# API keys and settings
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

# Communication
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")  # xapp-* for Socket Mode (connections:write)
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

# Payments
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

# Search (Tavily for web_search tool)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Substack (for publish_to_substack; optional SUBSTACK_PUBLICATION_URL)
SUBSTACK_SESSION_COOKIE = os.getenv("SUBSTACK_SESSION_COOKIE", "")
SUBSTACK_PUBLICATION_URL = os.getenv("SUBSTACK_PUBLICATION_URL", "")  # e.g. https://yoursubstack.substack.com

# Paths: life/ is relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
LIFE_ROOT = REPO_ROOT / "life"
