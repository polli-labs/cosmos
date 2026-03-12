#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="cosmos"
REPO_URL="${COSMOS_REPO_URL:-https://github.com/polli-labs/cosmos.git}"
DEV_ROOT="${COSMOS_DEV_ROOT:-$HOME/projects}"
TARGET_DIR="${COSMOS_TARGET_DIR:-$DEV_ROOT/$PROJECT_NAME}"
INSTALL_DOCS="${COSMOS_INSTALL_DOCS:-1}"
FORCE_CLONE="${COSMOS_FORCE_CLONE:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

log() {
  printf '==> %s\n' "$*"
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

ensure_path() {
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
  esac
}

sudo_prefix() {
  if [ "$(id -u)" -eq 0 ]; then
    return
  fi
  if have sudo; then
    printf 'sudo'
    return
  fi
  die "Root or sudo is required to install host packages on this machine."
}

ensure_homebrew() {
  if have brew; then
    return
  fi
  log "Installing Homebrew"
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  else
    die "Homebrew installation finished but brew was not found on PATH."
  fi
}

ensure_uv() {
  if have uv; then
    return
  fi
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ensure_path
  have uv || die "uv installation completed but uv is still not on PATH."
}

install_macos_prereqs() {
  ensure_homebrew
  log "Ensuring macOS prerequisites with Homebrew"
  have git || { brew list git >/dev/null 2>&1 || brew install git; }
  have ffmpeg || { brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg; }
  have python3 || { brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12; }
  have uv || { brew list uv >/dev/null 2>&1 || brew install uv; }
}

install_linux_prereqs() {
  local sudo_cmd
  sudo_cmd="$(sudo_prefix)"

  if have apt-get; then
    log "Ensuring Linux prerequisites with apt-get"
    $sudo_cmd apt-get update -y
    $sudo_cmd apt-get install -y git curl ca-certificates ffmpeg python3 python3-venv
    return
  fi

  if have dnf; then
    log "Ensuring Linux prerequisites with dnf"
    $sudo_cmd dnf install -y git curl ca-certificates ffmpeg python3
    return
  fi

  if have yum; then
    log "Ensuring Linux prerequisites with yum"
    $sudo_cmd yum install -y git curl ca-certificates ffmpeg python3
    return
  fi

  die "Unsupported Linux package manager. Install git, curl, python3, ffmpeg, and uv manually."
}

ensure_prereqs() {
  case "$(uname -s)" in
    Darwin)
      install_macos_prereqs
      ;;
    Linux)
      install_linux_prereqs
      ensure_uv
      ;;
    *)
      die "Unsupported OS: $(uname -s). This bootstrap script supports macOS and Linux."
      ;;
  esac
  ensure_path
  have git || die "git is required but was not found."
  have python3 || die "python3 is required but was not found."
  have ffmpeg || die "ffmpeg is required but was not found."
  have uv || die "uv is required but was not found."
}

reuse_embedded_repo() {
  [ "$FORCE_CLONE" = "1" ] && return 1
  [ -f "$REPO_ROOT/pyproject.toml" ] || return 1
  git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  TARGET_DIR="$REPO_ROOT"
  return 0
}

clone_or_reuse_repo() {
  if reuse_embedded_repo; then
    log "Reusing existing checkout at $TARGET_DIR"
    return
  fi

  mkdir -p "$(dirname "$TARGET_DIR")"
  if [ -d "$TARGET_DIR/.git" ]; then
    local existing_remote
    existing_remote="$(git -C "$TARGET_DIR" remote get-url origin 2>/dev/null || true)"
    if [ -n "$existing_remote" ] && [ "$existing_remote" != "$REPO_URL" ]; then
      die "Target directory already contains a git repo with a different origin: $existing_remote"
    fi
    log "Reusing existing clone at $TARGET_DIR"
    git -C "$TARGET_DIR" fetch --tags --prune
    return
  fi

  if [ -e "$TARGET_DIR" ]; then
    die "Target directory exists but is not a git checkout: $TARGET_DIR"
  fi

  log "Cloning $REPO_URL into $TARGET_DIR"
  git clone "$REPO_URL" "$TARGET_DIR"
}

sync_environment() {
  local -a sync_args
  sync_args=(sync --extra dev)
  if [ "$INSTALL_DOCS" = "1" ]; then
    sync_args+=(--extra docs)
  fi
  log "Syncing reproducible dev environment with uv"
  (
    cd "$TARGET_DIR"
    uv "${sync_args[@]}"
  )
}

print_next_steps() {
  cat <<EOF

Cosmos development environment is ready.

Project directory:
  $TARGET_DIR

Suggested next commands:
  cd "$TARGET_DIR"
  make check
  uv run cosmos --help

Optional docs build:
  cd "$TARGET_DIR"
  uv run mkdocs build

Optional environment override:
  export COSMOS_FFMPEG=/path/to/ffmpeg
EOF
}

main() {
  ensure_prereqs
  clone_or_reuse_repo
  sync_environment
  print_next_steps
}

main "$@"
