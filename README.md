# Alder

An autonomous AI agent at [aldergrow.com](https://aldergrow.com).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API keys in .env (Anthropic, OpenAI, Gemini, etc.)

# Run one agent cycle
python -m agent.agent_loop

# Run with a specific task
python -m agent.agent_loop --task "Research top AI stocks and log to daily notes"

# Run on a schedule (7 AM daily + every 4 hours)
python -m agent.agent_loop --daemon

# Chat with Alder in Slack (DM or @mention in a channel)
python -m agent.slack_bot
```

**Env vars** (in `.env`): LLM keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`); Slack (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`); optional `TAVILY_API_KEY` for web search; optional `SUBSTACK_SESSION_COOKIE` / `SUBSTACK_PUBLICATION_URL` for Substack.

## Chat with Alder in Slack

Run the Slack bot to talk to Alder in Slack. He replies in thread so you can have back-and-forth conversations and give him tasks (e.g. "update the mission to add X", "write a draft post for Substack").

1. **Slack app setup**
   - [Create a Slack app](https://api.slack.com/apps) (or use your existing one).
   - **Bot token**: OAuth & Permissions → add scopes `chat:write`, `app_mentions:read`, `im:history`, `channels:history` (if you want @mentions in channels). Install to workspace and put the **Bot User OAuth Token** (starts with `xoxb-`) in `.env` as `SLACK_BOT_TOKEN`.
   - **Socket Mode**: Settings → Socket Mode → Enable. Create an **App-Level Token** with scope `connections:write`. Put it in `.env` as `SLACK_APP_TOKEN` (starts with `xapp-`).
   - **Events**: Event Subscriptions → Enable. Under "Subscribe to bot events" add `message.im` (DMs) and `app_mention` (when someone @mentions the app in a channel).
   - **Optional**: Put `SLACK_CHANNEL_ID` in `.env` if the agent should be able to post to a default channel when asked.

2. **Run the bot**
   ```bash
   python -m agent.slack_bot
   ```
   Then DM the bot or @mention it in a channel; Alder will reply in thread.

## Architecture

```
agent/
├── agent_loop.py    ← the brain (wake, think, act, log)
├── tools.py         ← functions the agent can call (file ops under life/)
├── config.py        ← settings and API keys
life/
├── identity/        ← who Alder is (mission.md: mission, rules, personality)
├── daily/           ← daily note logs (one .md per day)
├── projects/        ← active initiatives
├── areas/           ← ongoing responsibilities
├── resources/       ← reference material
├── archives/        ← completed work
```

The landing page is `index.html` at the repo root.

## Deploy to DigitalOcean (Alder 24/7 + autonomous)

**1. Create a Droplet**

- Go to [cloud.digitalocean.com](https://cloud.digitalocean.com) → Create → Droplets.
- Image: **Ubuntu 24.04**. Plan: **Basic $6/mo** (or $12 if you want more headroom).
- Add your SSH key (or create one in DO). Create Droplet.

**2. SSH in and install Docker**

```bash
ssh root@YOUR_DROPLET_IP

# Install Docker
apt-get update && apt-get install -y docker.io
systemctl enable docker && systemctl start docker
```

**3. Clone the repo and add your `.env`**

```bash
cd /root
git clone https://github.com/YOUR_USERNAME/aldergrow.git
cd aldergrow
```

Create `.env` on the server with the same keys as locally (LLM, Slack, Substack, etc.). You can copy from your machine:

```bash
# From your Mac (in aldergrow/), copy .env to the droplet (replace IP):
scp .env root@YOUR_DROPLET_IP:/root/aldergrow/.env
```

**4. Build and run both services (Slack + daemon)**

```bash
cd /root/aldergrow
docker build -t aldergrow .

# Slack bot: listens 24/7 so you can chat with Alder
docker run -d --restart unless-stopped --name alder-slack --env-file .env aldergrow

# Daemon: runs agent cycle at 7 AM and every 4 hours (autonomous)
docker run -d --restart unless-stopped --name alder-daemon --env-file .env aldergrow python -m agent.agent_loop --daemon
```

**5. Check they’re running**

```bash
docker ps
```

You should see `alder-slack` and `alder-daemon`. Alder is now live: chat in Slack anytime; he’ll also run on schedule and can write Substack posts, log daily notes, etc.

**Updates later**

```bash
cd /root/aldergrow
git pull
bash scripts/do-start.sh
```

**Option: App Platform** — Connect the repo to DO App Platform, add a Worker running `python -m agent.slack_bot`, set env vars, deploy. For the daemon you’d add a second Worker running `python -m agent.agent_loop --daemon`, or trigger cycles from Slack only.
