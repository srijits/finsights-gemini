#!/bin/bash

# ============================================================================
# Update FinSights (Gemini Edition)
# ============================================================================
# Pulls latest changes from GitHub and restarts service
# Repository: https://github.com/srijits/finsights-gemini.git
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

FINSIGHTS_DIR="/home/ubuntu/finsights"
GIT_REPO="https://github.com/srijits/finsights-gemini.git"
SERVICE_NAME="finsights"

echo -e "${BLUE}"
echo "════════════════════════════════════════════════════════════"
echo "           UPDATE FINSIGHTS (GEMINI EDITION)                "
echo "════════════════════════════════════════════════════════════"
echo -e "${NC}"

cd "$FINSIGHTS_DIR"

# 1. Ensure correct remote
echo -e "${BLUE}[1/5] Checking git remote...${NC}"
if [ -d ".git" ]; then
    CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "none")
    if [ "$CURRENT_REMOTE" != "$GIT_REPO" ]; then
        echo -e "${YELLOW}  Updating remote to $GIT_REPO${NC}"
        git remote set-url origin "$GIT_REPO" 2>/dev/null || git remote add origin "$GIT_REPO"
    fi
    echo -e "${GREEN}  ✅ Remote: $GIT_REPO${NC}"
else
    echo -e "${YELLOW}  Not a git repo, cloning...${NC}"
    cd /home/ubuntu
    rm -rf finsights.bak
    mv finsights finsights.bak 2>/dev/null || true
    git clone "$GIT_REPO" finsights
    cd "$FINSIGHTS_DIR"
    echo -e "${GREEN}  ✅ Cloned fresh${NC}"
fi

# 2. Git pull
echo -e "${BLUE}[2/5] Pulling latest changes...${NC}"
git fetch origin
git reset --hard origin/main
echo -e "${GREEN}  ✅ Updated to latest${NC}"

# 3. Sync dependencies
echo -e "${BLUE}[3/5] Syncing dependencies...${NC}"
uv sync 2>/dev/null || .venv/bin/pip install -r requirements.txt
echo -e "${GREEN}  ✅ Dependencies synced${NC}"

# 4. Build CSS (if package.json exists)
echo -e "${BLUE}[4/5] Building frontend...${NC}"
if [ -f "package.json" ] && command -v npm &> /dev/null; then
    npm run build:css 2>/dev/null || echo -e "${YELLOW}  CSS build skipped${NC}"
fi
echo -e "${GREEN}  ✅ Frontend ready${NC}"

# 5. Restart service
echo -e "${BLUE}[5/5] Restarting service...${NC}"
sudo systemctl restart "$SERVICE_NAME"
echo -e "${GREEN}  ✅ Service restarted${NC}"

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                    UPDATE COMPLETE                          ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Status:"
systemctl status "$SERVICE_NAME" --no-pager -l | head -5
echo ""
