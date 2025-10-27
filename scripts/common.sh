#!/usr/bin/env bash
set -euo pipefail

slugify() {
  local input="$1"
  local slug
  slug=$(echo "$input" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')
  while [[ "$slug" == -* ]]; do
    slug=${slug#-}
  done
  while [[ "$slug" == *- ]]; do
    slug=${slug%-}
  done
  echo "$slug"
}

resolve_project_name() {
  local provided="$1"
  local name="$provided"
  if [[ -z "$name" ]]; then
    read -r -p "Project name (leave empty to skip): " name || true
  fi
  echo "$name"
}

resolve_repo_url() {
  local provided="$1"
  local url="$provided"
  if [[ -z "$url" ]]; then
    read -r -p "Git repository URL (leave empty to skip clone): " url || true
  fi
  echo "$url"
}

create_session_dir() {
  local project_name="$1"
  local timestamp
  timestamp=$(date +"%Y%m%d-%H%M%S")
  local slug
  slug=$(slugify "$project_name")
  local dir_name
  if [[ -n "$slug" ]]; then
    dir_name="${timestamp}-${slug}"
  else
    dir_name="${timestamp}"
  fi
  local session_dir="session/${dir_name}"
  mkdir -p session
  echo "$session_dir"
}

prepare_workspace() {
  local session_dir="$1"
  local repo_url="$2"
  if [[ -n "$repo_url" ]]; then
    git clone "$repo_url" "$session_dir"
  else
    mkdir -p "$session_dir"
  fi
}

apply_devcontainer_template() {
  local session_dir="$1"
  local project_name="$2"
  local template_path="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/templates/devcontainer.json.tpl"
  local devcontainer_dir="${session_dir}/.devcontainer"
  local target_file="${devcontainer_dir}/devcontainer.json"
  if [[ -f "$target_file" ]]; then
    return
  fi
  mkdir -p "$devcontainer_dir"
  local name="$project_name"
  if [[ -z "$name" ]]; then
    name="Android Dev Container"
  fi
  local escaped
  escaped=$(printf '%s' "$name" | sed 's/[\/&]/\\&/g')
  sed "s/__PROJECT_NAME__/${escaped}/g" "$template_path" > "$target_file"
}

open_with_editor() {
  local editor_cmd="$1"
  local fallback_cmd="$2"
  local session_dir="$3"
  if command -v "$editor_cmd" >/dev/null 2>&1; then
    "$editor_cmd" "$session_dir" &
    return 0
  fi
  if [[ -n "$fallback_cmd" ]]; then
    if command -v "$fallback_cmd" >/dev/null 2>&1; then
      "$fallback_cmd" "$session_dir" &
      return 0
    fi
  fi
  echo "Warning: Could not find an installed editor command to open ${session_dir}." >&2
  return 1
}
