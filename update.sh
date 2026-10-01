#!/usr/bin/env bash

# Exit immediately if any step fails
set -e

echo "🔄 Fetching the latest changes from GitHub..."
git pull origin main

# Confirm active execution inside virtual env or use standard local binary routing
if [ -n "$VIRTUAL_ENV" ]; then
    echo "📦 Upgrading package modules inside active virtual environment..."
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
    pip install -e .
else
    echo "⚠️ Warning: No active virtual environment detected. Updating global user profile space..."
    pip install --user --upgrade pip setuptools wheel
    pip install --user -r requirements.txt
    pip install --user -e .
fi

echo "✨ Update complete! All global binaries linked via setup.py are refreshed."
