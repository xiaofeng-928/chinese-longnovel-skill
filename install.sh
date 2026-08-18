#!/usr/bin/env bash
set -euo pipefail

platform="both"
repository="https://github.com/xiaofeng-928/chinese-longnovel-skill.git"
ref="master"
codex_home="${CODEX_HOME:-$HOME/.codex}"
claude_home="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

usage() {
  cat <<'EOF'
Usage: install.sh [options]

Options:
  --platform codex|claude|both  Install target (default: both)
  --repo URL                    Git repository URL
  --ref NAME                    Branch or tag (default: master)
  --codex-home PATH             Codex config directory
  --claude-home PATH            Claude Code config directory
  -h, --help                    Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform) platform="$2"; shift 2 ;;
    --repo) repository="$2"; shift 2 ;;
    --ref) ref="$2"; shift 2 ;;
    --codex-home) codex_home="$2"; shift 2 ;;
    --claude-home) claude_home="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$platform" in
  codex|claude|both) ;;
  *) echo "--platform must be codex, claude, or both." >&2; exit 2 ;;
esac

command -v git >/dev/null 2>&1 || {
  echo "Git is required. Install Git, then run this command again." >&2
  exit 1
}

install_mynovel() {
  local agent_name="$1"
  local agent_home="$2"
  local skills_dir="$agent_home/skills"
  local target="$skills_dir/my-novel"

  mkdir -p "$skills_dir"

  if [[ -e "$target" ]]; then
    if [[ ! -d "$target/.git" ]]; then
      echo "Target already exists and is not a Git checkout: $target" >&2
      exit 1
    fi

    echo "Updating MyNovel for $agent_name at $target"
    git -C "$target" fetch --depth 1 origin "$ref"
    git -C "$target" merge --ff-only FETCH_HEAD
  else
    echo "Installing MyNovel for $agent_name at $target"
    git clone --depth 1 --branch "$ref" "$repository" "$target"
  fi

  if [[ ! -f "$target/SKILL.md" ]]; then
    echo "Installation is incomplete: SKILL.md was not found at $target" >&2
    exit 1
  fi

  echo "Installed: $target"
}

if [[ "$platform" == "codex" || "$platform" == "both" ]]; then
  install_mynovel "Codex" "$codex_home"
fi

if [[ "$platform" == "claude" || "$platform" == "both" ]]; then
  install_mynovel "Claude Code" "$claude_home"
fi

echo "Restart the selected agent so it can discover the skill."
