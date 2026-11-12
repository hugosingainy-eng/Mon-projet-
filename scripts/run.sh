#!/usr/bin/env bash
# macOS / Linux equivalent of install.bat + start.bat
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -r requirements.txt
exec .venv/bin/python -m quantum_edge "$@"
