#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Bootstrap an AWS Lightsail instance to run the Triage Assistant
#
# Run this ONCE on a fresh Lightsail Ubuntu 22.04 instance:
#   chmod +x deploy.sh && sudo ./deploy.sh
#
# Then set your secrets:
#   sudo nano /opt/triage-assistant/.env
# =============================================================================
set -euo pipefail

APP_DIR="/opt/triage-assistant"
REPO_URL="${REPO_URL:-}"   # optional: set to your git remote to clone instead of copy

echo "==> [1/6] System update & Docker install"
apt-get update -qq
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release git

# Docker Engine (official repo)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable --now docker
echo "==> Docker $(docker --version) installed."

echo "==> [2/6] Create app directory"
mkdir -p "$APP_DIR"

if [[ -n "$REPO_URL" ]]; then
    echo "==> Cloning from $REPO_URL"
    git clone "$REPO_URL" "$APP_DIR"
else
    echo "==> No REPO_URL set — copy project files to $APP_DIR manually."
    echo "    Example: scp -r . ubuntu@<LIGHTSAIL_IP>:$APP_DIR"
fi

echo "==> [3/6] Create .env file (EDIT THIS before starting the app)"
cat > "$APP_DIR/.env" <<'EOF'
# ── Fill in your real values before running docker compose up ──
GOOGLE_API_KEY=your_gemini_api_key_here
GOOGLE_GEMINI_MODEL=gemini-2.0-flash
GROQ_API_KEY=
GROQ_MODEL=llama-3.1-8b-instant
EOF
chmod 600 "$APP_DIR/.env"
echo "    --> Edit $APP_DIR/.env now with your API keys!"

echo "==> [4/6] Open firewall port 8080 (Lightsail also needs it in the console)"
# UFW rules (Lightsail has its own firewall panel — add port 8080 there too)
ufw allow 22/tcp
ufw allow 8080/tcp
ufw --force enable

echo "==> [5/6] Install systemd service for auto-start on reboot"
cat > /etc/systemd/system/triage-assistant.service <<EOF
[Unit]
Description=Infrastructure Incident Triage Assistant
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable triage-assistant

echo "==> [6/6] Done!"
echo ""
echo "  Next steps:"
echo "  1. Edit your API keys:  sudo nano $APP_DIR/.env"
echo "  2. Start the app:       cd $APP_DIR && sudo docker compose up -d --build"
echo "  3. Check logs:          sudo docker compose logs -f"
echo "  4. Open in browser:     http://<YOUR_LIGHTSAIL_IP>:8080"
echo ""
echo "  First start takes ~3-5 minutes (model download + index build)."
echo "  Subsequent starts take <30 seconds."
