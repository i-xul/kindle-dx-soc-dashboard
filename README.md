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

## SSH / USBNetwork Breakthrough

USBNetwork was eventually successfully enabled on the Kindle DX Graphite.

The Kindle appears on the Raspberry Pi as a USB Ethernet gadget:

```text
usb0
Kindle IP: 192.168.2.2
Host IP:   192.168.2.1
```

SSH access works as root over USB Ethernet.

```bash
ssh root@192.168.2.2
```

This enables direct file transfer with `scp` and remote control experiments through Kindle's internal `lipc` interface.

### Current findings

- `scp` to `/mnt/us/linkss/screensavers/` works correctly.
- `/etc/init.d/framework restart` successfully restarts the Kindle framework.
- USB Ethernet networking works reliably through `g_ether`.
- `powerd` exposes properties such as:
  - `wakeUp`
  - `deferSuspend`
  - `touchScreenSaverTimeout`
  - `preventScreenSaver`
- `powerButton` is not available as a writable property on this firmware.
- `framework restart` alone does not automatically trigger screensaver mode.
- Automatic screensaver refresh without using the physical sleep button is still under investigation.

### Kindle system details

```text
Linux kindle 2.6.22.19-lab126 #3 PREEMPT Tue Jun 8 19:03:49 PDT 2010 armv6l unknown
```

```text
System Software Version: 008-TN2.1-049546
Tue Jun 8 19:07:59 PDT 2010
```

### Interesting mountpoints

```text
fsp on /opt/amazon/screen_saver/824x1200 type fuse.fsp
fsp on /mnt/us type fuse.fsp
```

These mountpoints appear to be directly related to the Kindle framework's screensaver handling.

## 📸 Preview

![Kindle DX Dashboard](images/dashboard-preview.jpg)

## Current Limitations

- Fully automatic screensaver refresh without using the physical sleep button is still under investigation.
- Kindle power management and screensaver triggering behavior are controlled by proprietary Lab126 framework components.
- Some `lipc` power management properties are readable but not writable on firmware 2.5.5.
- The Kindle framework does not automatically switch to screensaver mode after a framework restart.
- The project currently relies on a USB connection between the Raspberry Pi and the Kindle.

## Lessons Learned

- Kindle DX USB networking was unreliable on this specific firmware/device combination.
- Raspberry Pi OS Bullseye proved significantly more stable than newer Bookworm releases for this embedded use case.
- E-paper UI design requires much larger spacing and simpler layouts than traditional displays.
- USB mass-storage based updates turned out to be more reliable than attempting direct SSH control of the Kindle.

## Status

Working prototype.
