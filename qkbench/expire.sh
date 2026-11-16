#!/bin/bash
# Take the qkrylov benchmark page down: stop the container, remove the DNS record and tunnel route, drop the cron job.
# Run by cron on the expiry date, or by hand:  ./expire.sh
set -u
cd "$(dirname "$0")"
docker compose down
echo 'qkbench_enabled = false' > ../cloudflare/qkbench.auto.tfvars
( cd ../cloudflare && ./tofu.sh apply -auto-approve -input=false ) && echo "qkbench removed $(date)" >> expire.log
crontab -l 2>/dev/null | grep -v 'qkbench/expire.sh' | crontab -
