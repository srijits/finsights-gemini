#!/bin/bash

# ============================================================================
# Update FinSights
# ============================================================================
# Pulls latest changes and restarts service
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

FINSIGHTS_DIR="/home/ubuntu/finsights"
SERVICE_NAME="finsights"

echo -e "${BLUE}"
echo "════════════════════════════════════════════════════════════"
echo "           UPDATE FINSIGHTS                                 "
echo "════════════════════════════════════════════════════════════"
echo -e "${NC}"

cd "$FINSIGHTS_DIR"

# 1. Git pull
echo -e "${BLUE}[1/4] Pulling latest changes...${NC}"
git pull || echo -e "${YELLOW}  Git pull failed or not a repo${NC}"

# 2. Sync dependencies
echo -e "${BLUE}[2/4] Syncing dependencies...${NC}"
uv sync 2>/dev/null || .venv/bin/pip install -r requirements.txt
echo -e "${GREEN}  ✅ Dependencies synced${NC}"

# 3. Build CSS (if package.json exists)
echo -e "${BLUE}[3/4] Building frontend...${NC}"
if [ -f "package.json" ] && command -v npm &> /dev/null; then
    npm run build:css 2>/dev/null || echo -e "${YELLOW}  CSS build skipped${NC}"
fi
echo -e "${GREEN}  ✅ Frontend ready${NC}"

# 4. Restart service
echo -e "${BLUE}[4/4] Restarting service...${NC}"
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
