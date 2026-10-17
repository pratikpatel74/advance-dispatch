#!/bin/bash
# Deploy advance-dispatch to Hetzner server
# Usage: bash deploy.sh

SERVER="root@167.233.160.227"
REMOTE_DIR="/root/advance-dispatch"

echo "=== Deploying Advance Dispatch to $SERVER ==="

# Upload files
scp backend.py requirements.txt index.html "$SERVER:$REMOTE_DIR/"

# Install deps + restart Flask service + configure nginx
ssh "$SERVER" bash << 'REMOTE'
set -e
cd /root/advance-dispatch
pip install -r requirements.txt --break-system-packages --ignore-installed blinker -q

# ── Flask systemd service ─────────────────────────────────────────────────────
if [ ! -f /etc/systemd/system/advance-dispatch.service ]; then
cat > /etc/systemd/system/advance-dispatch.service << 'SVC'
[Unit]
Description=Advance Dispatch Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/advance-dispatch
ExecStart=/usr/bin/python3 /root/advance-dispatch/backend.py
Restart=always
RestartSec=5
Environment=PORT=3004
Environment=FLEET_BASE=http://localhost:3002
Environment=FLEET_JWT_SECRET=e4f52e8c10dc91fc320852a77caa6cea6c61cbc6bc5e5372bff7030ef6ba4107563b6cf9822a28886508466b6fae9f45019e68c616e2fa0ffc3f6a111220870e

[Install]
WantedBy=multi-user.target
SVC
systemctl daemon-reload
systemctl enable advance-dispatch
fi

systemctl restart advance-dispatch
sleep 2
systemctl is-active advance-dispatch && echo "✅ Backend running on port 3004" || echo "❌ Backend failed to start"

# ── nginx ─────────────────────────────────────────────────────────────────────
apt-get install -y nginx -q

# Copy frontend to web root
mkdir -p /var/www/advance-dispatch
cp /root/advance-dispatch/index.html /var/www/advance-dispatch/index.html

# Write nginx site config on port 81 (port 80 is H&S, port 8080 is Fleet Manager)
cat > /etc/nginx/sites-available/advance-dispatch << 'NGINX'
server {
    listen 81;
    server_name _;

    root /var/www/advance-dispatch;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

# Enable site only — do NOT touch default or any other site
ln -sf /etc/nginx/sites-available/advance-dispatch /etc/nginx/sites-enabled/advance-dispatch
nginx -t && systemctl restart nginx
systemctl is-active nginx && echo "✅ nginx serving frontend on port 81" || echo "❌ nginx failed to start"
REMOTE

echo ""
echo "=== Done ==="
echo "Frontend: http://167.233.160.227"
echo "Backend:  http://167.233.160.227:3004/health"
