#!/bin/bash
#
# Ralph Mode - One-Click Installer for macOS/Linux
# ================================================
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/sepehrbayat/copilot-ralph-mode/main/install.sh | bash
#
# Or download and run:
#   chmod +x install.sh
#   ./install.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║   🔄 Copilot Ralph Mode Installer                         ║"
echo "║                                                           ║"
echo "║   Iterative AI Development Loops for GitHub Copilot       ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python
echo -e "${BLUE}[1/5]${NC} Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION found"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION found"
else
    echo -e "  ${RED}✗${NC} Python not found!"
    echo ""
    echo "Please install Python 3.9 or later:"
    echo "  macOS:  brew install python3"
    echo "  Ubuntu: sudo apt install python3"
    echo "  Fedora: sudo dnf install python3"
    exit 1
fi

# Check Python version >= 3.9
PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo -e "  ${RED}✗${NC} Python 3.9 or later required (found $PYTHON_VERSION)"
    exit 1
fi

# Check Git
echo -e "${BLUE}[2/5]${NC} Checking Git installation..."
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo -e "  ${GREEN}✓${NC} Git $GIT_VERSION found"
else
    echo -e "  ${RED}✗${NC} Git not found!"
    echo ""
    echo "Please install Git:"
    echo "  macOS:  brew install git"
    echo "  Ubuntu: sudo apt install git"
    echo "  Fedora: sudo dnf install git"
    exit 1
fi

# Check GitHub Copilot CLI (optional)
echo -e "${BLUE}[3/5]${NC} Checking GitHub Copilot CLI..."
if command -v copilot &> /dev/null && copilot --version &> /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} GitHub Copilot CLI found"
else
    echo -e "  ${YELLOW}!${NC} GitHub Copilot CLI not found (optional)"
    echo "      Install later: npm install -g @github/copilot"
    echo "      Or (legacy): gh extension install github/gh-copilot"
fi

# Installation directory
INSTALL_DIR="${HOME}/.ralph-mode"
echo -e "${BLUE}[4/5]${NC} Installing to ${INSTALL_DIR}..."

# Clone or update repository
if [ -d "$INSTALL_DIR" ]; then
    echo "  Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet
else
    echo "  Cloning repository..."
    git clone --quiet https://github.com/sepehrbayat/copilot-ralph-mode.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi
echo -e "  ${GREEN}✓${NC} Repository ready"

# Make scripts executable
chmod +x ralph-loop.sh ralph-mode.sh ralph_mode.py 2>/dev/null || true

# Add to PATH
echo -e "${BLUE}[5/5]${NC} Setting up PATH..."

SHELL_RC=""
if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.profile" ]; then
    SHELL_RC="$HOME/.profile"
fi

if [ -n "$SHELL_RC" ]; then
    # Check if already in RC file
    if ! grep -q "ralph-mode" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# Ralph Mode - Iterative AI Development" >> "$SHELL_RC"
        echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$SHELL_RC"
        echo "alias ralph='python3 $INSTALL_DIR/ralph_mode.py'" >> "$SHELL_RC"
        echo -e "  ${GREEN}✓${NC} Added to $SHELL_RC"
    else
        echo -e "  ${GREEN}✓${NC} Already in $SHELL_RC"
    fi
else
    echo -e "  ${YELLOW}!${NC} Could not detect shell RC file"
    echo "      Add this to your shell config:"
    echo "      export PATH=\"\$PATH:$INSTALL_DIR\""
fi

# Done!
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}║   ✅ Installation Complete!                               ║${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Quick Start:${NC}"
echo ""
echo "  1. Restart your terminal or run:"
echo -e "     ${YELLOW}source $SHELL_RC${NC}"
echo ""
echo "  2. Navigate to your project:"
echo -e "     ${YELLOW}cd your-project${NC}"
echo ""
echo "  3. Start a Ralph loop:"
echo -e "     ${YELLOW}ralph enable \"Build a REST API\" --max-iterations 20${NC}"
echo -e "     ${YELLOW}./ralph-loop.sh${NC}"
echo ""
echo -e "${CYAN}Documentation:${NC}"
echo "  https://github.com/sepehrbayat/copilot-ralph-mode"
echo ""
