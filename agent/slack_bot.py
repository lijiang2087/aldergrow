"""Slack bot: Socket Mode listener (slack_bolt). Receives DMs and @mentions, passes to agent loop, posts reply."""

import re
import threading

from agent import config
from agent.agent_loop import run_one_cycle


def _strip_mention(text: str, bot_user_id: str) -> str:
    """Remove <@BOT_ID> from the start of text."""
    pattern = re.compile(rf"<@{re.escape(bot_user_id)}>\s*", re.IGNORECASE)
    return pattern.sub("", text).strip()


def _is_dm(message: dict, body: dict) -> bool:
    """Only handle direct messages to the bot (not channel messages without @mention)."""
    event = body.get("event", {})
    if event.get("bot_id"):
        return False
    return event.get("channel_type") == "im"


def _handle_dm(message: dict, say, logger):
    """DM received: run agent loop with message text as task, reply in thread."""
    text = (message.get("text") or "").strip()
    if not text:
        return
    ts = message.get("ts")
    channel = message.get("channel")

    def run_and_reply():
        try:
            logger.info("Running agent for DM: %s...", text[:50])
            reply_text = run_one_cycle(text)
            say(text=reply_text, thread_ts=ts)
            logger.info("Reply sent.")
        except Exception as e:
            logger.exception("Agent error: %s", e)
            try:
                say(text=f"Error: {e}", thread_ts=ts)
            except Exception:
                pass

    threading.Thread(target=run_and_reply, daemon=True).start()


def _handle_app_mention(event: dict, say, client, logger):
    """Channel @mention: strip mention, run agent loop, reply in thread."""
    text = (event.get("text") or "").strip()
    if not text:
        return
    auth = client.auth_test()
    bot_id = auth["user_id"]
    text = _strip_mention(text, bot_id)
    if not text.strip():
        return
    ts = event.get("ts")
    channel = event.get("channel")

    def run_and_reply():
        try:
            logger.info("Running agent for @mention: %s...", text[:50])
            reply_text = run_one_cycle(text)
            say(text=reply_text, thread_ts=ts)
            logger.info("Reply sent.")
        except Exception as e:
            logger.exception("Agent error: %s", e)
            try:
                say(text=f"Error: {e}", thread_ts=ts)
            except Exception:
                pass

    threading.Thread(target=run_and_reply, daemon=True).start()


def main() -> None:
    if not config.SLACK_BOT_TOKEN or not config.SLACK_APP_TOKEN:
        raise SystemExit(
            "Slack chat requires SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env. "
            "Enable Socket Mode in your Slack app and create an app-level token with connections:write."
        )

    import ssl
    import certifi
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    from slack_sdk.web import WebClient

    # SSL context for macOS (python.org install often has no system certs)
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    client = WebClient(token=config.SLACK_BOT_TOKEN, ssl=ssl_ctx)
    app = App(token=config.SLACK_BOT_TOKEN, client=client)

    @app.message(_is_dm)
    def on_dm(message, say, context):
        _handle_dm(message, say, context.logger)

    @app.event("app_mention")
    def on_mention(event, say, context):
        _handle_app_mention(event, say, context.client, context.logger)

    handler = SocketModeHandler(app, config.SLACK_APP_TOKEN)
    print("Alder is listening in Slack (slack_bolt). DM me or @mention me in a channel. Ctrl+C to stop.")
    handler.start()


if __name__ == "__main__":
    main()
