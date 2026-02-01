#!/bin/bash
# Run driver app (driverapp.py) - uses venv if present
cd "$(dirname "$0")"
if [ -d ".venv" ]; then
    .venv/bin/streamlit run driverapp.py --server.port 8502 "$@"
else
    streamlit run driverapp.py --server.port 8502 "$@"
fi
