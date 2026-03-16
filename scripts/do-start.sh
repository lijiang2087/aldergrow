#!/bin/bash
# Run on the DigitalOcean droplet (from /root/aldergrow) to start Slack bot + daemon.
set -e
cd "$(dirname "$0")/.."
docker build -t aldergrow .
docker stop alder-slack alder-daemon 2>/dev/null || true
docker rm alder-slack alder-daemon 2>/dev/null || true
docker run -d --restart unless-stopped --name alder-slack --env-file .env aldergrow
docker run -d --restart unless-stopped --name alder-daemon --env-file .env aldergrow python -m agent.agent_loop --daemon
echo "Started alder-slack and alder-daemon. Check: docker ps"
