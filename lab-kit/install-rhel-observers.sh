#!/bin/bash
set -euo pipefail
if [[ "$(hostname -s | tr '[:lower:]' '[:upper:]')" != "RHEL94-GUEST" ]]; then
  echo "Run only on RHEL94-GUEST." >&2; exit 1
fi
if [[ "$(id -u)" != "0" ]]; then echo "Run with sudo." >&2; exit 1; fi
getent group labadmin >/dev/null || { echo "Expected labadmin group is missing." >&2; exit 1; }
install -d -m 0750 -g labadmin /var/log/hv-demo
install -d -m 0750 /opt/hv-demo
cat > /opt/hv-demo/http-latency.sh <<'SCRIPT'
#!/bin/bash
export LC_ALL=C
while true; do
  sample=$(curl --max-time 5 -sS -o /dev/null -w '%{http_code} %{time_total}' http://localhost 2>/dev/null) || sample="000 5"
  read -r code seconds <<< "$sample"
  milliseconds=$(awk -v s="$seconds" 'BEGIN{printf "%.3f",s*1000}')
  printf '{"TimeGenerated":"%s","Computer":"RHEL94-GUEST","HttpCode":%d,"ResponseMs":%s}\n' \
    "$(date -u +%FT%TZ)" "$((10#$code))" "$milliseconds" >> /var/log/hv-demo/http-latency.json
  sleep 1
done
SCRIPT
chmod 0750 /opt/hv-demo/http-latency.sh
cat > /etc/systemd/system/hv-http-latency.service <<'UNIT'
[Unit]
Description=lightweight localhost HTTP latency observer
After=network-online.target nginx.service
[Service]
Type=simple
Group=labadmin
UMask=0027
ExecStart=/bin/bash /opt/hv-demo/http-latency.sh
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/logrotate.d/hv-http-latency <<'ROTATE'
/var/log/hv-demo/http-latency.json {
    daily
    size 50M
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
ROTATE
systemctl daemon-reload
systemctl enable --now hv-http-latency
echo "HTTP observer installed. The disk iostat observer is installed separately."
