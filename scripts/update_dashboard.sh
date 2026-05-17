#!/bin/bash

set -e

KINDLE_DEV="/dev/sda1"
MOUNT_POINT="/mnt/kindle"
PROJECT_DIR="/home/hmasi/kindle-dashboard"

cd "$PROJECT_DIR"

python3 dashboard.py

if [ ! -b "$KINDLE_DEV" ]; then
    echo "Kindle device not found at $KINDLE_DEV"
    echo "Reconnect Kindle USB cable or wake/reconnect the device, then run again."
    exit 1
fi

sudo mkdir -p "$MOUNT_POINT"

if ! mountpoint -q "$MOUNT_POINT"; then
    sudo mount "$KINDLE_DEV" "$MOUNT_POINT"
fi

sudo rm -f "$MOUNT_POINT/linkss/screensavers/"*
sudo cp "$PROJECT_DIR/dashboard.png" "$MOUNT_POINT/linkss/screensavers/"

sync

sudo umount "$MOUNT_POINT"

sleep 2
sudo udisksctl power-off -b /dev/sda || true

echo "Dashboard updated. Put Kindle to sleep to show the new image."
