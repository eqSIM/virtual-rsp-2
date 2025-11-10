#!/bin/bash
# Wrapper script for osmo-smdpp with PQC support
# Ensures liboqs shared library is found and venv is activated

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Set library path for liboqs
export DYLD_LIBRARY_PATH="$HOME/.local/lib:$DYLD_LIBRARY_PATH"

# Run osmo-smdpp
exec python3 osmo-smdpp.py "$@"

