# Alder: run Slack bot (or agent_loop) in a container. For DigitalOcean Droplet or App Platform.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ agent/
COPY life/ life/

# Default: run Slack bot so Alder is always listening. Override CMD to run agent_loop instead.
CMD ["python", "-m", "agent.slack_bot"]
