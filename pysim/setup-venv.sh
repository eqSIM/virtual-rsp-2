#!/bin/bash
# Setup Python virtual environment for pySim/osmo-smdpp

set -e

cd "$(dirname "$0")"

echo "=== Setting up Python environment for pySim ==="

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Python environment setup complete!"
echo "To activate: source pySim/venv/bin/activate"

