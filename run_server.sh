#!/bin/bash
# Run server app (App.py) - uses venv if present
cd "$(dirname "$0")"
if [ -d ".venv" ]; then
    .venv/bin/streamlit run App.py --server.port 8501 "$@"
else
    streamlit run App.py --server.port 8501 "$@"
fi
