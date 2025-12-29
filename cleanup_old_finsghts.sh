#!/bin/bash

# ============================================================================
# Cleanup OLD finsghts (typo) Installation
# ============================================================================
# Removes the old finsghts installation and stuck Certbot processes
# Run this BEFORE installing the new finsights
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

OLD_DIR="/home/ubuntu/finsghts"
DOMAIN="fin.afxo.in"
SERVICE_NAME="finsights"

echo -e "${RED}"
echo "════════════════════════════════════════════════════════════"
echo "     CLEANUP OLD FINSGHTS (typo) INSTALLATION              "
echo "════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}Please run with sudo${NC}"
    exit 1
fi

# ============================================================================
# Step 1: Kill stuck Certbot processes and remove lock files
# ============================================================================
echo -e "${BLUE}[1/5] Killing stuck Certbot processes...${NC}"
if pgrep -x certbot > /dev/null; then
    echo -e "${YELLOW}  Found running Certbot processes:${NC}"
    pgrep -a certbot
    pkill -9 certbot 2>/dev/null || true
    sleep 2
    echo -e "${GREEN}  ✅ Certbot processes killed${NC}"
else
    echo -e "${GREEN}  ✅ No running Certbot processes found${NC}"
fi

# Remove lock file
if [ -f "/var/lib/letsencrypt/.certbot.lock" ]; then
    rm -f /var/lib/letsencrypt/.certbot.lock
    echo -e "${GREEN}  ✅ Removed stale lock file${NC}"
fi

# Clean up temp certbot logs
rm -rf /tmp/certbot-log-* 2>/dev/null || true
echo -e "${GREEN}  ✅ Cleaned up temp files${NC}"

# ============================================================================
# Step 2: Stop and remove old service
# ============================================================================
echo -e "${BLUE}[2/5] Removing old service...${NC}"
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    echo -e "${GREEN}  ✅ Service stopped${NC}"
fi
if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
fi
rm -f "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
echo -e "${GREEN}  ✅ Service removed${NC}"

# ============================================================================
# Step 3: Remove nginx config
# ============================================================================
echo -e "${BLUE}[3/5] Removing nginx config...${NC}"
rm -f "/etc/nginx/sites-available/${DOMAIN}.conf"
rm -f "/etc/nginx/sites-enabled/${DOMAIN}.conf"
if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo -e "${GREEN}  ✅ Nginx config removed${NC}"
else
    echo -e "${YELLOW}  Nginx config check failed, skipping reload${NC}"
fi

# ============================================================================
# Step 4: Remove SSL certificate for domain
# ============================================================================
echo -e "${BLUE}[4/5] Removing SSL certificate...${NC}"
if [ -d "/etc/letsencrypt/live/$DOMAIN" ] || [ -d "/etc/letsencrypt/archive/$DOMAIN" ]; then
    # Try certbot delete first
    certbot delete --cert-name "$DOMAIN" --non-interactive 2>/dev/null || {
        # Fallback to manual removal
        echo -e "${YELLOW}  Certbot delete failed, removing manually...${NC}"
        rm -rf "/etc/letsencrypt/live/$DOMAIN"
        rm -rf "/etc/letsencrypt/archive/$DOMAIN"
        rm -f "/etc/letsencrypt/renewal/$DOMAIN.conf"
    }
    echo -e "${GREEN}  ✅ SSL certificate removed${NC}"
else
    echo -e "${YELLOW}  No SSL certificate found for $DOMAIN${NC}"
fi

# ============================================================================
# Step 5: Remove old directory (with typo)
# ============================================================================
echo -e "${BLUE}[5/5] Removing old directory...${NC}"
if [ -d "$OLD_DIR" ]; then
    echo -e "${YELLOW}  Found old directory: $OLD_DIR${NC}"
    read -p "  Remove old directory $OLD_DIR? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$OLD_DIR"
        echo -e "${GREEN}  ✅ Old directory removed${NC}"
    else
        echo -e "${YELLOW}  Old directory kept${NC}"
    fi
else
    echo -e "${GREEN}  ✅ No old directory found${NC}"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                  CLEANUP COMPLETE                           ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Cleaned up:"
echo "  ✅ Stuck Certbot processes"
echo "  ✅ Certbot lock files"
echo "  ✅ Old service: $SERVICE_NAME"
echo "  ✅ Old nginx config: $DOMAIN"
echo "  ✅ SSL certificate: $DOMAIN"
echo ""
echo -e "${BLUE}You can now run the install script:${NC}"
echo "  cd /home/ubuntu/finsights && sudo ./install_finsights.sh"
echo ""
