#!/bin/bash
# Deploy script for Gatekeeper
# Usage: sudo ./scripts/deploy.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_step() {
    echo -e "${GREEN}==>${NC} $1"
}

echo_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

echo_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

# Check if running as root (needed for systemctl and chown)
if [ "$EUID" -ne 0 ]; then
    echo_error "Please run with sudo: sudo ./scripts/deploy.sh"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo_step "Pulling latest changes from git..."
sudo -u ubuntu git pull

echo_step "Running database migrations..."
sudo -u ubuntu uv run all-migrations

echo_step "Building frontend..."
sudo -u ubuntu npm --prefix frontend run build

echo_step "Restarting gatekeeper service..."
systemctl restart gatekeeper

echo_step "Fixing frontend file ownership for nginx access..."
# Set ownership to ubuntu:www-data so both user and nginx can access
chown -R ubuntu:www-data "$PROJECT_DIR/frontend/dist"
# Ensure directories are traversable and files are readable
chmod -R 750 "$PROJECT_DIR/frontend/dist"
find "$PROJECT_DIR/frontend/dist" -type f -exec chmod 640 {} \;

echo_step "Checking nginx noindex protection for auth host..."
if grep -Rqs 'X-Robots-Tag "noindex, nofollow, noarchive"' /etc/nginx/sites-available; then
    echo -e "${GREEN}Auth noindex header found in nginx config.${NC}"
else
    echo_warning "No auth nginx config appears to send X-Robots-Tag: noindex. Update your Gatekeeper/auth server block to avoid search indexing."
fi

echo_step "Verifying gatekeeper service status..."
if systemctl is-active --quiet gatekeeper; then
    echo -e "${GREEN}Gatekeeper service is running.${NC}"
else
    echo_error "Gatekeeper service failed to start!"
    systemctl status gatekeeper --no-pager
    exit 1
fi

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
