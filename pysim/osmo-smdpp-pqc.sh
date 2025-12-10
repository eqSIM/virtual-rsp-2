#!/bin/bash
# Wrapper script for osmo-smdpp with PQC support
# Ensures liboqs shared library is found and venv is activated

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Set library path for liboqs (check multiple locations)
if [ -d "/opt/homebrew/lib" ]; then
    export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
elif [ -d "/usr/local/lib" ]; then
    export DYLD_LIBRARY_PATH="/usr/local/lib:$DYLD_LIBRARY_PATH"
fi

# Add user local lib as fallback
export DYLD_LIBRARY_PATH="$HOME/.local/lib:$DYLD_LIBRARY_PATH"

# Prevent auto-install attempts
export OQS_PYTHON_BUILD_SKIP_INSTALL=1

# Run osmo-smdpp
exec python3 osmo-smdpp.py "$@"

