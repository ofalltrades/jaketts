#!/usr/bin/env bash

set -e

echo "🚀 Starting installation for jaketts..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# --- SYSTEM COLLISION CHECKS ---
# Check if commands already exist and do NOT point to our directory
for cmd in "jaketts" "jtts"; do
    if command -v "$cmd" &> /dev/null; then
        # Check if the existing command is a symlink pointing elsewhere
        EXISTING_PATH=$(which "$cmd" || true)
        if [ -L "$EXISTING_PATH" ]; then
            TARGET_PATH=$(readlink "$EXISTING_PATH" || true)
            # If it points to our folder, it's just an update, which is fine
            if [[ "$TARGET_PATH" == *"$SCRIPT_DIR"* ]]; then
                continue
            fi
        fi
        
        echo "⚠️ Warning: A command named '$cmd' already exists at $EXISTING_PATH"
        read -p "Do you want to overwrite it? (y/N): " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            echo "❌ Installation aborted by user to prevent command collision."
            exit 1
        fi
    fi
done

echo "🔒 Adjusting permissions..."
chmod +x jaketts.py

echo "🔗 Creating command shortcuts (requires sudo permissions)..."
sudo ln -sf "$SCRIPT_DIR/jaketts.py" /usr/local/bin/jaketts
sudo ln -sf "$SCRIPT_DIR/jaketts.py" /usr/local/bin/jtts

echo "🎉 Success! Global shortcuts are successfully linked."
