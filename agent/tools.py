"""Functions the agent can call. File ops are restricted to the life/ tree; Slack/Telegram etc. use config."""

from datetime import date
from pathlib import Path

from agent.config import (
    LIFE_ROOT,
    SLACK_BOT_TOKEN,
    SLACK_CHANNEL_ID,
    TAVILY_API_KEY,
    SUBSTACK_SESSION_COOKIE,
    SUBSTACK_PUBLICATION_URL,
    X_API_KEY,
    X_API_SECRET,
    X_ACCESS_TOKEN,
    X_ACCESS_TOKEN_SECRET,
)


def _daily_path() -> Path:
    """Path for today's daily note: life/daily/YYYY-MM-DD.md"""
    today = date.today()
    return LIFE_ROOT / "daily" / f"{today.isoformat()}.md"


def _resolve(path: str) -> Path:
    """Resolve path under life/; raise if it escapes."""
    full = (LIFE_ROOT / path).resolve()
    if not str(full).startswith(str(LIFE_ROOT.resolve())):
        raise ValueError(f"Path must be under life/: {path}")
    return full


def read_file(path: str) -> str:
    """Read a file under life/. path is relative to life/."""
    p = _resolve(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    return p.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> None:
    """Write content to a file under life/. path is relative to life/. Creates parent dirs if needed."""
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def list_dir(path: str = "") -> list[str]:
    """List entries in a directory under life/. path is relative to life/ (default: life/ itself)."""
    p = _resolve(path) if path else LIFE_ROOT
    if not p.is_dir():
        raise NotADirectoryError(str(p))
    return [x.name for x in sorted(p.iterdir(), key=lambda x: x.name)]


def read_today_notes() -> str:
    """Read today's daily log. Returns empty string if the file does not exist yet."""
    p = _daily_path()
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8")


def write_daily_note(content: str) -> str:
    """Append content to today's daily log. Creates the file if it does not exist. Use for logging tasks, decisions, and outcomes."""
    p = _daily_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    line = f"\n\n---\n[{datetime.now().isoformat()}]\n{content}"
    if p.exists():
        p.write_text(p.read_text(encoding="utf-8") + line, encoding="utf-8")
    else:
        p.write_text(line.lstrip(), encoding="utf-8")
    return "Appended to today's daily log"


def web_search(query: str) -> str:
    """Search the web for current information. Use for research, prices, news, or facts."""
    if not TAVILY_API_KEY:
        raise RuntimeError("Web search is not configured. Set TAVILY_API_KEY in .env (get one at tavily.com).")
    import requests
    resp = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        return "No results found."
    lines = []
    for r in results:
        title = r.get("title", "")
        url = r.get("url", "")
        content = r.get("content", "")[:500]
        lines.append(f"**{title}**\n{url}\n{content}")
    return "\n\n".join(lines)


def publish_to_substack(title: str, body: str, subtitle: str = "") -> str:
    """Publish a post to Substack (Alder Capital). Uses SUBSTACK_SESSION_COOKIE and SUBSTACK_PUBLICATION_URL if set; otherwise saves draft to life/resources/substack_drafts/."""
    from datetime import datetime
    import re
    safe = re.sub(r"[^\w\s-]", "", title).strip()[:50]
    safe = re.sub(r"[-\s]+", "-", safe)
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    draft_path = f"resources/substack_drafts/{date_prefix}-{safe or 'post'}.md"
    content = f"# {title}\n\n"
    if subtitle:
        content += f"**{subtitle}**\n\n"
    content += body
    # Always save a local copy for records
    try:
        write_file(draft_path, content)
    except Exception as e:
        pass  # non-fatal

    if SUBSTACK_SESSION_COOKIE and SUBSTACK_PUBLICATION_URL:
        try:
            from substack import Api
            from substack.post import Post
            api = Api(
                cookies_string=SUBSTACK_SESSION_COOKIE.strip(),
                publication_url=SUBSTACK_PUBLICATION_URL.strip().rstrip("/"),
            )
            user_id = api.get_user_id()
            post = Post(title=title, subtitle=subtitle or "", user_id=user_id, audience="everyone", write_comment_permissions="everyone")
            post.from_markdown(content, api=api)
            draft = api.post_draft(post.get_draft())
            api.prepublish_draft(draft.get("id"))
            api.publish_draft(draft.get("id"))
            return f"Published to Substack ({SUBSTACK_PUBLICATION_URL}). Draft copy saved to life/{draft_path}."
        except Exception as e:
            return f"Substack publish failed: {e}. Draft saved to life/{draft_path}; publish manually via dashboard."

    return f"Draft saved to life/{draft_path}. Set SUBSTACK_SESSION_COOKIE and SUBSTACK_PUBLICATION_URL in .env to publish automatically."


def get_payment_info() -> str:
    """Return USDC payment instructions (addresses per network + memo instruction). Use when someone asks how to pay Alder in USDC or for wallet addresses."""
    return read_file("identity/wallet.md")


def post_to_x(text: str) -> str:
    """Post a tweet from Alder's X/Twitter account. Text must be ≤280 characters. Use when the user or mission asks to post to X/Twitter."""
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
        raise RuntimeError(
            "X/Twitter is not configured. Set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, and X_ACCESS_TOKEN_SECRET in .env. "
            "See README for how to connect Alder's X account."
        )
    text = (text or "").strip()
    if not text:
        raise ValueError("Tweet text cannot be empty.")
    if len(text) > 280:
        raise ValueError(f"Tweet must be ≤280 characters (got {len(text)}).")
    import tweepy
    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
    )
    resp = client.create_tweet(text=text)
    if resp and getattr(resp, "data", None):
        tid = resp.data.get("id", "")
        return f"Posted to X (tweet id: {tid})."
    return "Posted to X."


def send_slack_message(text: str, channel: str | None = None) -> str:
    """Send a message to Slack. Uses SLACK_CHANNEL_ID if channel is not provided."""
    if not SLACK_BOT_TOKEN:
        raise RuntimeError("Slack is not configured. Set SLACK_BOT_TOKEN (and optionally SLACK_CHANNEL_ID) in .env")
    ch = channel or SLACK_CHANNEL_ID
    if not ch:
        raise ValueError("No channel specified and SLACK_CHANNEL_ID is not set in .env")
    from slack_sdk import WebClient
    client = WebClient(token=SLACK_BOT_TOKEN)
    client.chat_postMessage(channel=ch, text=text)
    return "Message sent to Slack"


# Tool definitions for LLM function calling (Anthropic and OpenAI compatible shape)
# Keep post_to_x near the top so the model reliably sees it in the tool list.
TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "send_slack_message",
        "description": "Send a message to the configured Slack channel. Use this when the user asks to post or send something to Slack.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The message text to send to Slack"},
                "channel": {"type": "string", "description": "Optional Slack channel ID or name (e.g. #general). Omit to use SLACK_CHANNEL_ID from .env."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "post_to_x",
        "description": "Post a tweet from Alder's X/Twitter account. Use when the user or mission asks to post to X/Twitter. Keep text ≤280 characters.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Tweet text (max 280 characters)."}},
            "required": ["text"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file under life/ (e.g. identity/mission.md, daily/2025-01-15.md). Path is relative to life/.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path relative to life/, e.g. identity/mission.md"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file under life/. Creates parent directories if needed. Path is relative to life/.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to life/"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List entries (files and folders) in a directory under life/. Path is relative to life/; use empty string for life/ itself.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path relative to life/, or empty for root of life/"}},
            "required": [],
        },
    },
    {
        "name": "read_today_notes",
        "description": "Read today's daily log (life/daily/YYYY-MM-DD.md). Use to see what has already been logged today before adding more.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_daily_note",
        "description": "Append a log entry to today's daily note. Use to record tasks completed, decisions made, revenue, errors, and outcomes.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string", "description": "The log entry to append (plain text or markdown)."}},
            "required": ["content"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web for current information. Use for research, stock prices, news, or any facts that need to be up to date.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query."}},
            "required": ["query"],
        },
    },
    {
        "name": "publish_to_substack",
        "description": "Publish a post to Alder's Substack (Alder Capital). Call this when writing a new post. Saves a draft to life/resources/substack_drafts/; operator can publish via Substack dashboard or API can be wired later. For financial content always include the required disclaimer (see mission).",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Post title."},
                "body": {"type": "string", "description": "Post body (markdown)."},
                "subtitle": {"type": "string", "description": "Optional subtitle."},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "get_payment_info",
        "description": "Get USDC payment instructions (addresses for Ethereum, Base, Arbitrum + memo instruction). Use when someone asks how to pay Alder in USDC or for wallet addresses.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def run_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments. Returns result string or raises."""
    if name == "send_slack_message":
        return send_slack_message(
            text=arguments["text"],
            channel=arguments.get("channel"),
        )
    if name == "read_file":
        return read_file(path=arguments["path"])
    if name == "write_file":
        write_file(path=arguments["path"], content=arguments["content"])
        return "File written."
    if name == "list_dir":
        return str(list_dir(path=arguments.get("path", "")))
    if name == "read_today_notes":
        return read_today_notes()
    if name == "write_daily_note":
        return write_daily_note(content=arguments["content"])
    if name == "web_search":
        return web_search(query=arguments["query"])
    if name == "publish_to_substack":
        return publish_to_substack(
            title=arguments["title"],
            body=arguments["body"],
            subtitle=arguments.get("subtitle", ""),
        )
    if name == "get_payment_info":
        return get_payment_info()
    if name == "post_to_x":
        return post_to_x(text=arguments["text"])
    raise ValueError(f"Unknown tool: {name}")
