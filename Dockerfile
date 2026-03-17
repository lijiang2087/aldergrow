# Alder: run Slack bot (or agent_loop) in a container. For DigitalOcean Droplet or App Platform.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ agent/
COPY life/ life/
COPY scripts/ scripts/
COPY index.html .

EXPOSE 5000

CMD ["python", "-m", "agent.slack_bot"]
