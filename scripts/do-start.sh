#!/bin/bash
# Run on the DigitalOcean droplet (from /root/aldergrow) to start all services.
# Usage: bash scripts/do-start.sh
set -e
cd "$(dirname "$0")/.."

docker build -t aldergrow .

docker stop alder-slack alder-daemon alder-site 2>/dev/null || true
docker rm   alder-slack alder-daemon alder-site 2>/dev/null || true

docker run -d --restart unless-stopped --name alder-slack  --env-file .env aldergrow
docker run -d --restart unless-stopped --name alder-daemon --env-file .env aldergrow python -m agent.agent_loop --daemon
docker run -d --restart unless-stopped --name alder-site   --env-file .env -e PORT=80 -p 80:80 aldergrow python scripts/serve_site.py

echo "Started alder-slack, alder-daemon, alder-site (:5000). Check: docker ps"
