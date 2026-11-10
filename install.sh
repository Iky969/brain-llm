#!/usr/bin/env bash
set -e

# 🧠 Brain LLM Installer
# Quick install: curl -fsSL https://raw.githubusercontent.com/Iky969/brain-llm/main/install.sh | bash

REPO="Iky969/brain-llm"
BRANCH="main"
INSTALL_DIR="${HOME}/.local/share/brain-llm"
BIN_DIR="${HOME}/.local/bin"

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
DIM="\033[2m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}🧠 Installing Brain LLM...${RESET}"

# 1. Check Python
if ! command -v python3 &>/dev/null; then
  echo -e "${YELLOW}❌ python3 is required but not found in PATH.${RESET}"
  exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  echo -e "${YELLOW}❌ Python 3.9+ is required (found Python ${PY_VER}).${RESET}"
  exit 1
fi

# 2. Check for git or curl/tar
mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"

APP_SRC="${INSTALL_DIR}/source"
VENV_DIR="${INSTALL_DIR}/venv"

echo -e "${DIM}→ Fetching latest Brain source from ${REPO}...${RESET}"

if command -v git &>/dev/null; then
  if [ -d "${APP_SRC}/.git" ]; then
    (cd "${APP_SRC}" && git fetch origin && git reset --hard origin/${BRANCH})
  else
    rm -rf "${APP_SRC}"
    git clone --depth 1 --branch "${BRANCH}" "https://github.com/${REPO}.git" "${APP_SRC}"
  fi
else
  rm -rf "${APP_SRC}"
  mkdir -p "${APP_SRC}"
  curl -fsSL "https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz" | tar -xz -C "${APP_SRC}" --strip-components=1
fi

# 3. Create Virtualenv to avoid PEP 668 externally managed environment issues
echo -e "${DIM}→ Setting up virtual environment in ${VENV_DIR}...${RESET}"
if [ ! -d "${VENV_DIR}" ]; then
  python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -e "${APP_SRC}"

# 4. Create symlink in ~/.local/bin
ln -sf "${VENV_DIR}/bin/brain" "${BIN_DIR}/brain"

echo -e "\n${GREEN}${BOLD}✅ Brain installed successfully!${RESET}"
echo -e "${DIM}Executable placed at: ${BIN_DIR}/brain${RESET}"

# 5. Check PATH
case ":$PATH:" in
  *":${BIN_DIR}:"*) ;;
  *)
    echo -e "\n${YELLOW}⚠️  Notice: ${BIN_DIR} is not in your PATH.${RESET}"
    echo -e "Add it to your shell configuration:"
    echo -e "  ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    echo -e "Run this or add it to ${BOLD}~/.bashrc${RESET} or ${BOLD}~/.zshrc${RESET}."
    ;;
esac

echo -e "\n${CYAN}To get started:${RESET}"
echo -e "  ${BOLD}brain init${RESET}           # Initialize your vault (~/.brain)"
echo -e "  ${BOLD}brain core${RESET}           # View core soul memory"
echo -e "  ${BOLD}brain new \"My Note\"${RESET}  # Create a knowledge note"
echo -e "  ${BOLD}brain repl${RESET}           # Enter interactive shell\n"
