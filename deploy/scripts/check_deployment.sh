#!/usr/bin/env bash
set -euo pipefail

echo "Checking systemd service..."
systemctl is-active --quiet literature-screening
systemctl status literature-screening --no-pager --lines=12

echo "Checking Streamlit local endpoint..."
curl -fsS http://127.0.0.1:8502 >/dev/null
echo "Streamlit responded on 127.0.0.1:8502"

echo "Checking Nginx config..."
nginx -t

echo "Checking disk usage..."
df -h /opt/literature-screening-data || true

echo "Deployment checks passed."
