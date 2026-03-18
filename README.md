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

**Env vars** (in `.env`): LLM keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`); Slack (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL_ID`); optional `TAVILY_API_KEY` for web search; optional `SUBSTACK_SESSION_COOKIE` / `SUBSTACK_PUBLICATION_URL` for Substack; optional X/Twitter (`X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`) for posting as Alder.

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

## Connect Alder's X/Twitter account

To let Alder post tweets (e.g. via the `post_to_x` tool when you ask in Slack or in the daemon), connect the X account that will represent Alder:

1. **Create or use an X account** that will be “Alder” (e.g. @AlderCapital or your chosen handle). Log in at [x.com](https://x.com).

2. **Developer access**
   - Go to [developer.x.com](https://developer.x.com) and sign in with that account (or the one that will own the app).
   - Create a **Project** and an **App** (or use an existing app).
   - In the app, open **Settings → User authentication** and turn it **On**. Set type to “Read and write” (so the app can post). Set Callback URL to something like `https://localhost` (we only need the tokens once; you can use a placeholder). Save.

3. **Keys and tokens**
   - In the app, go to **Keys and tokens**.
   - **Consumer keys**: note the **API Key** and **API Key Secret** (create if needed).
   - **Authentication**: under “Access Token and Secret”, click **Generate**. Authorize the app with the account that should post as Alder. Copy the **Access Token** and **Access Token Secret**.

4. **Add these 4 lines to `.env`** (all from the **OAuth 1.0 Keys** section only; ignore OAuth 2.0 / Client ID / Client Secret):

   | # | In `.env` | In X Developer Portal (Keys and tokens → OAuth 1.0 Keys) |
   |---|-----------|----------------------------------------------------------------|
   | 1 | `X_API_KEY=` | **Consumer Key** (click Show to reveal) |
   | 2 | `X_API_SECRET=` | **Consumer Secret** (same section; Show or Regenerate) |
   | 3 | `X_ACCESS_TOKEN=` | **Access Token** (click Generate for “For @AlderGrow”; copy the token) |
   | 4 | `X_ACCESS_TOKEN_SECRET=` | **Access Token Secret** (shown once when you Generate the Access Token; copy it) |

   Example (replace with your real values; X labels the first two “Consumer Key” and “Consumer Secret”):
   ```bash
   X_API_KEY=your_consumer_key_here
   X_API_SECRET=your_consumer_secret_here
   X_ACCESS_TOKEN=your_access_token_here
   X_ACCESS_TOKEN_SECRET=your_access_token_secret_here
   ```
   Keep these secret; don’t commit `.env`. Restart the Slack bot and/or daemon so they pick up the new vars. Alder can then use the `post_to_x` tool when you ask him to post to X/Twitter.

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

The landing page is `index.html` at the repo root. To show the **latest tweet text** (not just the Twitter timeline embed) on the page, run the site server; it serves the static site and an API that uses your X credentials to fetch recent tweets:

```bash
python scripts/serve_site.py
```

Then open http://localhost:5000 . The left column will show the latest tweets (text, date, link). If `/api/tweets` isn’t available (e.g. you open the HTML file directly), the page falls back to the Twitter timeline embed. On the droplet you can run this in a separate container or behind nginx and point aldergrow.com at it.

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

**Shared `life/`** — All three containers mount the host’s `life/` folder (`./life` on the droplet). Alder’s Slack/daemon writes and the website read the same files (tweets log, shop products, daily notes). Edit shop files on the server under `/root/aldergrow/life/` or let Alder update them via tools.

**Updates later**

```bash
cd /root/aldergrow
git pull
bash scripts/do-start.sh
```

**Option: App Platform** — Connect the repo to DO App Platform, add a Worker running `python -m agent.slack_bot`, set env vars, deploy. For the daemon you’d add a second Worker running `python -m agent.agent_loop --daemon`, or trigger cycles from Slack only.
