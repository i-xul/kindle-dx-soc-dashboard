#!/bin/bash

set -e

PROJECT_DIR="/home/hmasi/kindle-dashboard"
KINDLE_HOST="root@192.168.2.2"
KINDLE_KEY="/home/hmasi/.ssh/id_rsa"
KINDLE_SCREEN_DIR="/mnt/us/linkss/screensavers"

cd "$PROJECT_DIR"

python3 dashboard.py

scp -i "$KINDLE_KEY" dashboard.png "$KINDLE_HOST:$KINDLE_SCREEN_DIR/"

STATE=$(ssh -i "$KINDLE_KEY" "$KINDLE_HOST" "lipc-get-prop com.lab126.powerd state" | tr -d '\r')

echo "Kindle power state: $STATE"

if [ "$STATE" = "active" ]; then
    ssh -i "$KINDLE_KEY" "$KINDLE_HOST" "powerd_test -p"
    echo "Kindle moved to screensaver mode."
elif [ "$STATE" = "screenSaver" ]; then
    ssh -i "$KINDLE_KEY" "$KINDLE_HOST" "powerd_test -p"
    sleep 3
    ssh -i "$KINDLE_KEY" "$KINDLE_HOST" "powerd_test -p"
    echo "Kindle refreshed screensaver mode."
else
    echo "Unknown Kindle power state: $STATE"
    echo "Not toggling power button."
fi

echo "Dashboard updated."
