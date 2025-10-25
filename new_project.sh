#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
WORKSPACE_ROOT="$ROOT_DIR/workspace"
TEMPLATE_ROOT="$ROOT_DIR/templates"
PROJECT_NAME=""
EDITOR=""
TEMPLATE="android"
RUNTIME=""

usage() {
  cat <<'USAGE'
Usage: ./new_project.sh [options] <project-name>

Options:
  --editor <code|fleet>   Open the project with the specified editor after creation.
  --template <name>       Template to use (default: android).
  --runtime <docker|podman>
                         Container runtime preference. Auto-detected when omitted.
  -h, --help              Show this help message and exit.
USAGE
}

slugify() {
  local text="$1"
  text="${text,,}"
  text="$(echo "$text" | tr ' ' '-' | tr -cs 'a-z0-9-_' '-')"
  text="${text##-}"
  text="${text%%-}"
  if [[ -z "$text" ]]; then
    text="project"
  fi
  printf '%s' "$text"
}

escape_sed() {
  printf '%s' "$1" | sed -e 's/[&/\\]/\\&/g'
}

pick_runtime() {
  if [[ -n "$RUNTIME" ]]; then
    echo "$RUNTIME"
    return
  fi

  if command -v docker >/dev/null 2>&1; then
    echo "docker"
    return
  fi

  if command -v podman >/dev/null 2>&1; then
    echo "podman"
    return
  fi

  echo ""
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --editor)
      shift
      EDITOR="${1:-}"
      if [[ -z "$EDITOR" ]]; then
        echo "Error: --editor requires a value" >&2
        exit 1
      fi
      ;;
    --template)
      shift
      TEMPLATE="${1:-}"
      if [[ -z "$TEMPLATE" ]]; then
        echo "Error: --template requires a value" >&2
        exit 1
      fi
      ;;
    --runtime)
      shift
      RUNTIME="${1:-}"
      if [[ -z "$RUNTIME" ]]; then
        echo "Error: --runtime requires a value" >&2
        exit 1
      fi
      ;;
    --*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      if [[ -n "$PROJECT_NAME" ]]; then
        echo "Error: multiple project names provided" >&2
        usage >&2
        exit 1
      fi
      PROJECT_NAME="$1"
      ;;
  esac
  shift
done

if [[ -z "$PROJECT_NAME" ]]; then
  echo "Error: project name is required" >&2
  usage >&2
  exit 1
fi

if [[ ! -d "$TEMPLATE_ROOT/$TEMPLATE" ]]; then
  echo "Error: template '$TEMPLATE' was not found under $TEMPLATE_ROOT" >&2
  exit 1
fi

mkdir -p "$WORKSPACE_ROOT"

TIMESTAMP="$(date +"%Y%m%d-%H%M%S")"
SLUG="$(slugify "$PROJECT_NAME")"
TARGET_DIR="$WORKSPACE_ROOT/${TIMESTAMP}-${SLUG}"

if [[ -e "$TARGET_DIR" ]]; then
  echo "Error: target directory $TARGET_DIR already exists" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

if command -v rsync >/dev/null 2>&1; then
  rsync -a "$TEMPLATE_ROOT/$TEMPLATE/" "$TARGET_DIR/"
else
  cp -a "$TEMPLATE_ROOT/$TEMPLATE/." "$TARGET_DIR/"
fi

PROJECT_ESCAPED="$(escape_sed "$PROJECT_NAME")"
SLUG_ESCAPED="$(escape_sed "$SLUG")"
RUNTIME_VALUE="$(pick_runtime)"
RUNTIME_PLACEHOLDER="${RUNTIME_VALUE:-auto}"
RUNTIME_ESCAPED="$(escape_sed "$RUNTIME_PLACEHOLDER")"

if command -v rg >/dev/null 2>&1; then
  mapfile -t files < <(rg --files --hidden --no-ignore "$TARGET_DIR")
else
  mapfile -t files < <(find "$TARGET_DIR" -type f)
fi

for file in "${files[@]}"; do
  sed -i "s/__PROJECT_TITLE__/$PROJECT_ESCAPED/g" "$file"
  sed -i "s/__PROJECT_SLUG__/$SLUG_ESCAPED/g" "$file"
  sed -i "s/__PROJECT_TIMESTAMP__/$TIMESTAMP/g" "$file"
  sed -i "s/__PROJECT_RUNTIME__/$RUNTIME_ESCAPED/g" "$file"
done

cat <<INFO
Created project at: $TARGET_DIR
Template: $TEMPLATE
INFO

if [[ -z "$RUNTIME_VALUE" ]]; then
  echo "Warning: No container runtime (docker or podman) detected. Please install one before opening the dev container." >&2
else
  echo "Detected container runtime: $RUNTIME_VALUE"
fi

if command -v devcontainer >/dev/null 2>&1; then
  if [[ -z "$RUNTIME_VALUE" ]]; then
    echo "Skipping 'devcontainer up' because no container runtime is available." >&2
  else
    echo "Bringing up dev container (this may take a moment)..."
    if ! devcontainer up --workspace-folder "$TARGET_DIR"; then
      echo "Warning: 'devcontainer up' failed. You can retry from your editor once prerequisites are installed." >&2
    fi
  fi
else
  echo "Tip: Install the 'devcontainer' CLI to pre-build the container. Skipping automatic build." >&2
fi

case "$EDITOR" in
  "code")
    if command -v code >/dev/null 2>&1; then
      code "$TARGET_DIR"
    else
      echo "Warning: VS Code (code) command not found. Please open the folder manually." >&2
    fi
    ;;
  "fleet")
    if command -v fleet >/dev/null 2>&1; then
      fleet "$TARGET_DIR"
    else
      echo "Warning: JetBrains Fleet CLI not found. Please open the folder manually." >&2
    fi
    ;;
  "")
    ;;
  *)
    echo "Warning: Unknown editor '$EDITOR'. Supported values are 'code' or 'fleet'." >&2
    ;;
 esac

cat <<'NEXT_STEPS'
Next steps:
  1. Open the folder with your editor of choice (VS Code or Fleet).
  2. Reopen the folder in the container if your editor prompts you.
  3. Start building your Android application!
NEXT_STEPS

