#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt -c constraints.txt
printf 'Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.\n'
exec .venv/bin/python -m stillflow serve
