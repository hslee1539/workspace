#!/usr/bin/env bash
set -euo pipefail

USERNAME="${DEVCONTAINER_USERNAME:-vscode}"
HOME_DIR="/home/${USERNAME}"

sudo chown -R "${USERNAME}:${USERNAME}" "$HOME_DIR"

mkdir -p "$HOME_DIR/.android" "$HOME_DIR/.gradle"

sudo chown -R "${USERNAME}:${USERNAME}" "$HOME_DIR/.android" "$HOME_DIR/.gradle"

sudo -u "$USERNAME" env HOME="$HOME_DIR" bash <<'INNER'
set -euo pipefail
touch "$HOME/.android/repositories.cfg"
yes | sdkmanager --licenses >/dev/null 2>&1 || true
sdkmanager --update >/dev/null 2>&1 || true
INNER

echo "Android SDK is ready for __PROJECT_TITLE__."
