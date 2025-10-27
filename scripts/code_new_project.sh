#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

repo_url="${1:-}"
project_name="${2:-}"

repo_url=$(resolve_repo_url "$repo_url")
project_name=$(resolve_project_name "$project_name")

session_dir=$(create_session_dir "$project_name")
prepare_workspace "$session_dir" "$repo_url"
apply_devcontainer_template "$session_dir" "$project_name"

if [[ -z "$repo_url" ]]; then
  echo "Initialized empty project at ${session_dir}."
else
  echo "Cloned ${repo_url} into ${session_dir}."
fi

if [[ -z "$project_name" ]]; then
  project_name="${session_dir##*/}"
fi

if ! open_with_editor "code" "code-insiders" "$session_dir"; then
  if [[ "$(uname)" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
    open -a "Visual Studio Code" "$session_dir" || true
  else
    echo "Warning: VS Code command line tools not found. Open ${session_dir} manually." >&2
  fi
fi
