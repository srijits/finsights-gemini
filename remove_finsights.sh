#!/bin/bash

# ============================================================================
# Remove FinSights
# ============================================================================
# Removes FinSights service, nginx config, and SSL certificate
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

FINSIGHTS_DIR="/home/ubuntu/finsights"
DOMAIN="fin.afxo.in"
SERVICE_NAME="finsights"

echo -e "${RED}"
echo "════════════════════════════════════════════════════════════"
echo "           REMOVE FINSIGHTS                                 "
echo "════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}Please run with sudo${NC}"
    exit 1
fi

echo -e "${RED}⚠️  WARNING: This will remove:${NC}"
echo "  - Systemd service: $SERVICE_NAME"
echo "  - Nginx config: $DOMAIN"
echo "  - SSL certificate: $DOMAIN"
echo "  - Directory: $FINSIGHTS_DIR (optional)"
echo ""
read -p "Type 'yes' to confirm: " confirm

if [[ ! "$confirm" =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Removal cancelled.${NC}"
    exit 0
fi

# 0. Kill any stuck Certbot processes
echo -e "${BLUE}[0/4] Killing any stuck Certbot processes...${NC}"
pkill -9 certbot 2>/dev/null || true
rm -f /var/lib/letsencrypt/.certbot.lock 2>/dev/null || true
echo -e "${GREEN}  ✅ Certbot cleaned${NC}"

# 1. Stop and remove service
echo -e "${BLUE}[1/4] Removing systemd service...${NC}"
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
echo -e "${GREEN}  ✅ Service removed${NC}"

# 2. Remove nginx config
echo -e "${BLUE}[2/4] Removing nginx config...${NC}"
rm -f "/etc/nginx/sites-available/${DOMAIN}.conf"
rm -f "/etc/nginx/sites-enabled/${DOMAIN}.conf"
nginx -t && systemctl reload nginx
echo -e "${GREEN}  ✅ Nginx config removed${NC}"

# 3. Remove SSL certificate
echo -e "${BLUE}[3/4] Removing SSL certificate...${NC}"
if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    certbot delete --cert-name "$DOMAIN" --non-interactive 2>/dev/null || {
        rm -rf "/etc/letsencrypt/live/$DOMAIN"
        rm -rf "/etc/letsencrypt/archive/$DOMAIN"
        rm -f "/etc/letsencrypt/renewal/$DOMAIN.conf"
    }
    echo -e "${GREEN}  ✅ Certificate removed${NC}"
else
    echo -e "${YELLOW}  No certificate found${NC}"
fi

# 4. Optionally remove directory
echo ""
read -p "Also remove directory $FINSIGHTS_DIR? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$FINSIGHTS_DIR"
    echo -e "${GREEN}  ✅ Directory removed${NC}"
else
    echo -e "${YELLOW}  Directory kept${NC}"
fi

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                  REMOVAL COMPLETE                           ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
