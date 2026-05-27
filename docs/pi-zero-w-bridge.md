# Raspberry Pi Zero W Bridge Mode

This document describes the standalone Raspberry Pi Zero W bridge setup used by the Kindle DX SOC Dashboard project.

The original prototype was developed on a Raspberry Pi 3.  
The project was later migrated to a Raspberry Pi Zero W to make the system smaller, more self-contained, and closer to a standalone embedded appliance.

---

## Architecture

```text
Raspberry Pi 4 / monitored server
        |
        | WiFi / LAN
        v
Raspberry Pi Zero W
        |
        | USB Ethernet
        v
Kindle DX Graphite
```

The Kindle DX does not use native WiFi for this project.

Instead, the Raspberry Pi Zero W acts as the network-aware bridge device.

---

## Responsibilities of the Pi Zero W

The Pi Zero W handles:

- connecting to the home network over WiFi
- collecting telemetry from the monitored Raspberry Pi 4 over SSH
- generating the dashboard image with Python and Pillow
- transferring the rendered image to the Kindle over SCP
- triggering Kindle screensaver refreshes over SSH
- running the refresh workflow automatically through systemd timers

---

## Why Pi Zero W?

The Pi Zero W is well suited for this role because it provides:

- built-in WiFi
- Linux userspace
- SSH/SCP support
- Python support
- systemd support
- micro-USB OTG support
- very low power consumption
- small physical footprint

A microcontroller such as an Arduino Uno or Raspberry Pi Pico is not suitable for this role because the project relies on Linux networking, SSH, SCP, Python image rendering, and systemd automation.

---

## USB Ethernet Layout

The Kindle is connected to the Pi Zero W through USB.

The Kindle remains in USBNetwork mode and exposes itself as a USB Ethernet device.

Working addressing:

```text
Pi Zero W usb0: 192.168.2.1/24
Kindle DX:      192.168.2.2
```

Manual setup:

```bash
sudo ip link set usb0 up
sudo ip addr add 192.168.2.1/24 dev usb0
```

Connectivity test:

```bash
ping -c 3 192.168.2.2
```

SSH test:

```bash
ssh -i ~/.ssh/id_rsa root@192.168.2.2 hostname
```

Expected result:

```text
kindle
```

---

## Persistent USB Ethernet Configuration

A systemd service is used to configure the USB Ethernet interface after boot.

Location:

```text
/etc/systemd/system/kindle-usbnet.service
```

Service file:

```ini
[Unit]
Description=Configure Kindle USB Ethernet interface
After=network.target
Wants=network.target

[Service]
Type=oneshot
ExecStart=/sbin/ip link set usb0 up
ExecStart=/bin/sh -c '/sbin/ip addr show dev usb0 | /bin/grep -q "192.168.2.1/24" || /sbin/ip addr add 192.168.2.1/24 dev usb0'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kindle-usbnet.service
sudo systemctl start kindle-usbnet.service
```

Check status:

```bash
systemctl status kindle-usbnet.service
```

Expected state:

```text
active (exited)
```

---

## Dashboard Refresh Timer

The Pi Zero W runs the dashboard refresh script through a user-level systemd timer.

The refresh process:

1. Generates a fresh `dashboard.png`
2. Transfers it to the Kindle over SCP
3. Checks Kindle power state through `lipc`
4. Triggers the required screensaver refresh through `powerd_test`

The timer runs every 15 minutes.

Check timer status:

```bash
systemctl --user list-timers
systemctl --user status kindle-dashboard.timer
```

Manual refresh test:

```bash
systemctl --user start kindle-dashboard.service
systemctl --user status kindle-dashboard.service
```

Successful output includes:

```text
status=0/SUCCESS
Kindle refreshed screensaver mode.
Dashboard updated.
```

---

## Current Result

The current working setup is:

```text
Raspberry Pi 4
    ↓
WiFi / LAN
    ↓
Raspberry Pi Zero W
    ↓
USB Ethernet
    ↓
Kindle DX Graphite
```

This effectively turns the Kindle DX into a standalone low-power e-paper SOC dashboard.

The Kindle only needs to remain connected to the Pi Zero W, while the Pi Zero W handles networking, rendering, automation, and refresh control.

---

## Notes

The Kindle DX Graphite does not appear to expose a normal WiFi interface under this firmware.

When wireless is enabled on the Kindle itself, the system exposes PPP/modem-related components rather than a standard WLAN interface.

Observed indicators:

```text
ppp0
ppp_async
ppp_generic
option
usbserial
mwan
```

No usable `wlan0` interface or WiFi kernel modules were found.

Because of this, the Pi Zero W bridge approach is currently the most practical wireless-style architecture.
