#!/bin/sh
set -eu

mkdir -p /app/data /app/uploads /app/exports /var/log/nginx /var/lib/nginx /run/nginx

nginx

exec streamlit run /app/app/main.py --server.address=0.0.0.0 --server.port="${STREAMLIT_SERVER_PORT:-8502}"
