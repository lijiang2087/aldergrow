"""Slack bot: Socket Mode listener (slack_bolt). Receives DMs and @mentions, passes to agent loop, posts reply."""

import re
import threading

from agent import config
from agent.agent_loop import run_one_cycle

# Dedupe: avoid replying twice to the same message (Slack can deliver the same event more than once)
_replied_ts: set[tuple[str, str]] = set()
_replied_lock = threading.Lock()
_MAX_REPLIED = 500  # cap size so the set doesn't grow forever


def _already_handled(channel: str, ts: str) -> bool:
    with _replied_lock:
        key = (channel, ts)
        if key in _replied_ts:
            return True
        _replied_ts.add(key)
        if len(_replied_ts) > _MAX_REPLIED:
            _replied_ts.clear()
        return False


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
    """DM received: run agent loop with message text as task, reply inline in the DM."""
    # Skip Slack-generated message subtypes (joins, etc.)
    st = message.get("subtype") or ""
    if st in ("channel_join", "channel_leave", "group_join", "group_leave", "message_changed", "message_deleted"):
        return
    text = (message.get("text") or "").strip()
    if not text and message.get("files"):
        text = "[User shared a file or attachment — acknowledge and help if you can.]"
    if not text:
        return
    ts = message.get("ts")
    channel = message.get("channel")
    if _already_handled(channel, ts):
        logger.info("Skipping duplicate DM channel=%s ts=%s", channel, ts)
        print(f"[alder-slack] Skipping duplicate DM channel={channel} ts={ts}", flush=True)
        return
    print(f"[alder-slack] Received DM channel={channel} ts={ts} text={text[:80]!r}", flush=True)

    def run_and_reply():
        try:
            logger.info("Running agent for DM: %s...", text[:50])
            print(f"[alder-slack] Running agent for DM: {text[:80]!r}", flush=True)
            reply_text = run_one_cycle(text)
            # Slack truncates around 40k; split if needed
            if len(reply_text) > 35000:
                reply_text = reply_text[:35000] + "\n\n_(truncated)_"
            say(text=reply_text)
            logger.info("Reply sent.")
            print("[alder-slack] DM reply sent.", flush=True)
        except Exception as e:
            logger.exception("Agent error: %s", e)
            try:
                say(text=f"Error: {e}")
            except Exception:
                pass
            print(f"[alder-slack] DM error: {e}", flush=True)

    threading.Thread(target=run_and_reply, daemon=True).start()


def _handle_app_mention(event: dict, say, client, logger):
    """Channel @mention: strip mention, run agent loop, reply in thread."""
    text = (event.get("text") or "").strip()
    if not text:
        return
    ts = event.get("ts")
    channel = event.get("channel")
    if _already_handled(channel, ts):
        logger.info("Skipping duplicate @mention channel=%s ts=%s", channel, ts)
        print(f"[alder-slack] Skipping duplicate mention channel={channel} ts={ts}", flush=True)
        return
    auth = client.auth_test()
    bot_id = auth["user_id"]
    text = _strip_mention(text, bot_id)
    if not text.strip():
        return

    def run_and_reply():
        try:
            logger.info("Running agent for @mention: %s...", text[:50])
            print(f"[alder-slack] Running agent for mention: {text[:80]!r}", flush=True)
            reply_text = run_one_cycle(text)
            say(text=reply_text, thread_ts=ts)
            logger.info("Reply sent.")
            print("[alder-slack] Mention reply sent.", flush=True)
        except Exception as e:
            logger.exception("Agent error: %s", e)
            try:
                say(text=f"Error: {e}", thread_ts=ts)
            except Exception:
                pass
            print(f"[alder-slack] Mention error: {e}", flush=True)

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

    @app.event("message")
    def on_message(event, say, context):
        # Only handle DMs. (channel_type sometimes missing in thread replies — DM channels start with D)
        if event.get("bot_id"):
            return
        ch = event.get("channel") or ""
        is_dm = event.get("channel_type") == "im" or (
            ch.startswith("D") and not ch.startswith("C")
        )
        if not is_dm:
            return
        print(
            f"[alder-slack] message event channel={event.get('channel')} ts={event.get('ts')} "
            f"thread_ts={event.get('thread_ts')} subtype={event.get('subtype')!r}",
            flush=True,
        )
        _handle_dm(event, say, context.logger)

    @app.event("app_mention")
    def on_mention(event, say, context):
        _handle_app_mention(event, say, context.client, context.logger)

    handler = SocketModeHandler(app, config.SLACK_APP_TOKEN)
    print("Alder is listening in Slack (slack_bolt). DM me or @mention me in a channel. Ctrl+C to stop.")
    handler.start()


if __name__ == "__main__":
    main()
