#!/bin/bash
#
# Kindle DX SOC Dashboard
#
# Author: H A (i-xul)
# Repository: https://github.com/i-xul/kindle-dx-soc-dashboard
#
# Created: 2026-05-19
# Current version: v1.0.0
#
# Description:
# Generates and deploys the latest dashboard image to the Kindle DXG.
#

set -e

PROJECT_DIR="/home/hmasi/kindle-dashboard"
KINDLE_HOST="root@192.168.2.2"
KINDLE_IP="192.168.2.2"
KINDLE_KEY="/home/hmasi/.ssh/id_rsa"
KINDLE_SCREEN_DIR="/mnt/us/linkss/screensavers"

SSH_OPTS="-i $KINDLE_KEY -o BatchMode=yes -o ConnectTimeout=5"

cd "$PROJECT_DIR"

if ! ping -c 1 -W 3 "$KINDLE_IP" >/dev/null 2>&1; then
    echo "Kindle is not reachable at $KINDLE_IP. Skipping refresh."
    exit 0
fi

python3 dashboard.py

scp $SSH_OPTS dashboard.png "$KINDLE_HOST:$KINDLE_SCREEN_DIR/"

ssh $SSH_OPTS "$KINDLE_HOST" \
    "/usr/sbin/eips -f -g $KINDLE_SCREEN_DIR/dashboard.png"

echo "Dashboard refreshed with eips."
echo "Dashboard updated."

# STATE=$(ssh -i "$KINDLE_KEY" "$KINDLE_HOST" "lipc-get-prop com.lab126.powerd state" | tr -d '\r')

# echo "Kindle power state: $STATE"

# if [ "$STATE" = "active" ]; then
#     ssh -i "$KINDLE_KEY" "$KINDLE_HOST" "powerd_test -p"
#     echo "Kindle moved to screensaver mode."
# elif [ "$STATE" = "screenSaver" ]; then
#     ssh -i "$KINDLE_KEY" "$KINDLE_HOST" "powerd_test -p"
#     sleep 3
#     ssh -i "$KINDLE_KEY" "$KINDLE_HOST" "powerd_test -p"
#     echo "Kindle refreshed screensaver mode."
# else
#     echo "Unknown Kindle power state: $STATE"
#     echo "Not toggling power button."
# fi

ssh -i "$KINDLE_KEY" "$KINDLE_HOST" \
    "/usr/sbin/eips -f -g /mnt/us/linkss/screensavers/dashboard.png"

echo "Dashboard refreshed with eips."

echo "Dashboard updated."
