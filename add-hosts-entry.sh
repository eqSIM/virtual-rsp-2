#!/bin/bash
# Add hosts entry for osmo-smdpp
# This script requires sudo password

echo "Adding testsmdpplus1.example.com to /etc/hosts..."

if grep -q "testsmdpplus1.example.com" /etc/hosts 2>/dev/null; then
    echo "Entry already exists in /etc/hosts"
else
    echo "127.0.0.1  testsmdpplus1.example.com" | sudo tee -a /etc/hosts
    echo "Entry added successfully"
fi

