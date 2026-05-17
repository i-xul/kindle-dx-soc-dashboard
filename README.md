# Kindle DX SOC Dashboard

A repurposed Amazon Kindle DX Graphite used as an e-paper SOC-style dashboard for monitoring self-hosted Raspberry Pi infrastructure.

The dashboard is rendered with Python and Pillow on a Raspberry Pi 3, copied to the Kindle over USB mass storage, and displayed through the Kindle's custom screensaver system.

## Features

- 9.7" e-paper infrastructure dashboard
- Raspberry Pi 3 based image rendering
- Kindle DX Graphite repurposing
- Python + Pillow dashboard generation
- Remote Fail2ban status over SSH
- Docker container status over SSH
- Nginx/security log section prepared for future use
- USB mass-storage based update pipeline

## Hardware

- Amazon Kindle DX Graphite
- Raspberry Pi 3
- USB cable
- Raspberry Pi OS Lite Legacy / Bullseye

## Current Architecture

```text
Remote server / Raspberry Pi infrastructure
        |
        | SSH
        v
Raspberry Pi 3
        |
        | Python dashboard renderer
        v
dashboard.png
        |
        | USB mass storage
        v
Kindle DX Graphite screensaver
```

## 📸 Preview

![Kindle DX Dashboard](images/dashboard-preview.jpg)

## Current Limitations
Kindle USBNetwork/SSH was tested but not working reliably on this device.
The current update method uses USB mass storage.
After updating, the Kindle must enter sleep mode before the refreshed dashboard is displayed.
Fully automatic refresh is planned as future work.

## Lessons Learned

- Kindle DX USB networking was unreliable on this specific firmware/device combination.
- Raspberry Pi OS Bullseye proved significantly more stable than newer Bookworm releases for this embedded use case.
- E-paper UI design requires much larger spacing and simpler layouts than traditional displays.
- USB mass-storage based updates turned out to be more reliable than attempting direct SSH control of the Kindle.

## Status

Working prototype.
