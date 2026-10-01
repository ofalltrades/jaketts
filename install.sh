#!/usr/bin/env bash

# Exit immediately if any command fails
set -e

echo "🚀 Starting installation for jaketts..."

# 1. Ensure the script is running from its root folder layout context
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# 2. Make the core engine files executable locally
echo "🔒 Adjusting permissions..."
chmod +x jaketts.py

# 3. Create systemic symlinks in /usr/local/bin
echo "🔗 Creating command shortcuts (requires sudo permissions)..."
# Link the primary binary
sudo ln -sf "$SCRIPT_DIR/jaketts.py" /usr/local/bin/jaketts

# Link the requested alias binary (jtts)
sudo ln -sf "$SCRIPT_DIR/jaketts.py" /usr/local/bin/jtts

echo "🎉 Success! You can now run the following commands globally from any directory:"
echo "   👉 jaketts \"Your text here\""
echo "   👉 jtts \"Your text here\""
