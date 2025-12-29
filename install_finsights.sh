#!/bin/bash

# ============================================================================
# Install FinSights Service
# ============================================================================
# Clones and installs FinSights news platform at fin.afxo.in on port 8501
# Repository: https://github.com/marketcalls/FinSights.git
# Uses uv for Python package management
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
FINSIGHTS_DIR="/home/ubuntu/finsights"
GIT_REPO="https://github.com/marketcalls/FinSights.git"
DOMAIN="fin.afxo.in"
PORT="8501"
SERVICE_NAME="finsights"

echo -e "${BLUE}"
echo "════════════════════════════════════════════════════════════"
echo "           INSTALL FINSIGHTS SERVICE                        "
echo "════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}Please run with sudo${NC}"
    exit 1
fi

# ============================================================================
# Step 0: Install uv if not present
# ============================================================================
echo -e "${BLUE}[0/8] Installing uv package manager...${NC}"

# Check if uv is installed
if ! command -v uv &> /dev/null && [ ! -f "/home/ubuntu/.local/bin/uv" ]; then
    echo -e "${CYAN}  Installing uv...${NC}"
    sudo -u ubuntu bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    echo -e "${GREEN}  ✅ uv installed${NC}"
else
    echo -e "${GREEN}  ✅ uv already installed${NC}"
fi

# Set uv path
if [ -f "/snap/bin/uv" ]; then
    UV_BIN="/snap/bin/uv"
elif [ -f "/home/ubuntu/.local/bin/uv" ]; then
    UV_BIN="/home/ubuntu/.local/bin/uv"
else
    UV_BIN="uv"
fi
echo -e "${CYAN}  Using uv at: $UV_BIN${NC}"

# ============================================================================
# Step 1: Kill any stuck Certbot processes
# ============================================================================
echo -e "${BLUE}[1/8] Checking for stuck Certbot processes...${NC}"
if pgrep -x certbot > /dev/null; then
    echo -e "${YELLOW}  Found running Certbot process, killing...${NC}"
    pkill -9 certbot 2>/dev/null || true
    sleep 2
fi
rm -f /var/lib/letsencrypt/.certbot.lock 2>/dev/null || true
echo -e "${GREEN}  ✅ Certbot check complete${NC}"

# ============================================================================
# Step 2: Check that code directory exists (no git pull - code must be copied manually)
# ============================================================================
echo -e "${BLUE}[2/8] Checking code directory...${NC}"

if [ ! -d "$FINSIGHTS_DIR" ]; then
    echo -e "${RED}  ❌ Directory $FINSIGHTS_DIR does not exist!${NC}"
    echo -e "${YELLOW}  Please copy the finsights code to $FINSIGHTS_DIR first.${NC}"
    echo -e "${YELLOW}  Example: scp -r ./finsights ubuntu@server:/home/ubuntu/${NC}"
    exit 1
fi

if [ ! -f "$FINSIGHTS_DIR/app/main.py" ]; then
    echo -e "${RED}  ❌ app/main.py not found in $FINSIGHTS_DIR${NC}"
    echo -e "${YELLOW}  Please ensure the complete finsights code is copied.${NC}"
    exit 1
fi

chown -R ubuntu:ubuntu "$FINSIGHTS_DIR"
echo -e "${GREEN}  ✅ Code directory verified${NC}"

# ============================================================================
# Step 3: Setup Python Environment with uv
# ============================================================================
echo -e "${BLUE}[3/8] Setting up Python environment with uv...${NC}"
cd "$FINSIGHTS_DIR"

# Create pyproject.toml if it doesn't exist (required for uv)
if [ ! -f "pyproject.toml" ]; then
    echo -e "${CYAN}  Creating pyproject.toml for uv...${NC}"
    sudo -u ubuntu cat > pyproject.toml << 'PYTOML'
[project]
name = "finsights"
version = "1.0.0"
description = "AI-powered financial news platform"
requires-python = ">=3.10"
dependencies = [
    "fastapi",
    "uvicorn",
    "jinja2",
    "python-multipart",
    "sqlalchemy",
    "aiosqlite",
    "python-dotenv",
    "google-genai>=1.0.0",
    "apscheduler",
    "bcrypt",
    "python-jose",
    "httpx",
    "cryptography",
    "pytz",
    "itsdangerous",
    "markdown",
    "bleach",
]

[tool.uv]
dev-dependencies = []
PYTOML
    chown ubuntu:ubuntu pyproject.toml
fi

# Create or sync venv using uv
echo -e "${CYAN}  Installing dependencies with uv...${NC}"
sudo -u ubuntu $UV_BIN sync 2>/dev/null || {
    echo -e "${YELLOW}  uv sync failed, trying uv pip install...${NC}"
    sudo -u ubuntu $UV_BIN venv .venv
    sudo -u ubuntu $UV_BIN pip install -r requirements.txt
}
echo -e "${GREEN}  ✅ Python environment ready${NC}"

# ============================================================================
# Step 4: Build frontend CSS (optional)
# ============================================================================
echo -e "${BLUE}[4/8] Building frontend CSS...${NC}"
if command -v npm &> /dev/null; then
    cd "$FINSIGHTS_DIR"
    sudo -u ubuntu npm install 2>/dev/null || echo -e "${YELLOW}  npm install skipped${NC}"
    sudo -u ubuntu npm run build:css 2>/dev/null || echo -e "${YELLOW}  CSS build skipped (may already be built)${NC}"
    echo -e "${GREEN}  ✅ Frontend ready${NC}"
else
    echo -e "${YELLOW}  npm not found, skipping CSS build${NC}"
fi

# ============================================================================
# Step 5: Create data directory
# ============================================================================
echo -e "${BLUE}[5/8] Creating data directories...${NC}"
mkdir -p "$FINSIGHTS_DIR/data"
chown -R ubuntu:ubuntu "$FINSIGHTS_DIR/data"
echo -e "${GREEN}  ✅ Data directory ready${NC}"

# ============================================================================
# Step 6: Install systemd service using uv run
# ============================================================================
echo -e "${BLUE}[6/8] Installing systemd service...${NC}"

cat > /etc/systemd/system/finsights.service << EOF
[Unit]
Description=FinSights News Service (Port $PORT)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=$FINSIGHTS_DIR
ExecStart=$UV_BIN run uvicorn app.main:app --host 127.0.0.1 --port $PORT
Environment="PATH=/home/ubuntu/.local/bin:/snap/bin:/usr/local/bin:/usr/bin:/bin"
Environment="HOME=/home/ubuntu"
Restart=always
RestartSec=5

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable finsights
systemctl restart finsights
echo -e "${GREEN}  ✅ Service installed and started${NC}"

# ============================================================================
# Step 7: Setup nginx
# ============================================================================
echo -e "${BLUE}[7/8] Configuring nginx...${NC}"

# Create initial config for SSL
cat > /etc/nginx/sites-available/${DOMAIN}.conf << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name fin.afxo.in;
    root /var/www/html;
    
    location / {
        return 200 'FinSights';
        add_header Content-Type text/plain;
    }
}
EOF

ln -sf /etc/nginx/sites-available/${DOMAIN}.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
echo -e "${GREEN}  ✅ Initial nginx config created${NC}"

# Get SSL certificate
echo -e "${BLUE}  Obtaining SSL certificate...${NC}"
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo -e "${GREEN}  ✅ SSL certificate already exists${NC}"
else
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@afxo.in
    
    if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        echo -e "${RED}  ❌ Failed to obtain SSL certificate${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✅ SSL certificate obtained${NC}"
fi

# ============================================================================
# Step 8: Configure final nginx
# ============================================================================
echo -e "${BLUE}[8/8] Configuring final nginx...${NC}"

cat > /etc/nginx/sites-available/${DOMAIN}.conf << EOF
# FinSights - fin.afxo.in

server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;
    
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
EOF

nginx -t && systemctl reload nginx
echo -e "${GREEN}  ✅ Nginx configured${NC}"

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                  INSTALLATION COMPLETE                      ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Repository:"
echo "  • $GIT_REPO"
echo "  • Installed at: $FINSIGHTS_DIR"
echo ""
echo "Python Environment (uv):"
echo "  • uv binary: $UV_BIN"
echo "  • Virtual env: $FINSIGHTS_DIR/.venv"
echo ""
echo "Service:"
echo "  • finsights → Port $PORT"
echo "  • Uses: uv run uvicorn"
echo ""
echo "URL:"
echo "  • https://$DOMAIN"
echo "  • Admin: https://$DOMAIN/admin (admin/admin123)"
echo ""
echo "Commands:"
echo "  systemctl status finsights"
echo "  journalctl -u finsights -f"
echo "  cd $FINSIGHTS_DIR && uv run python -c 'print(\"test\")'"
echo ""
echo -e "${YELLOW}NOTE: Change admin password after first login!${NC}"
echo ""
