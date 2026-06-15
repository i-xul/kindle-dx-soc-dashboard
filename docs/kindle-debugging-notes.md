# Kindle DX Debugging Notes

This document contains engineering notes and troubleshooting details collected while building the Kindle DX infrastructure dashboard project.

The project combines:

- Amazon Kindle DX Graphite
- Raspberry Pi 3
- Python/Pillow dashboard rendering
- SSH automation
- Kindle USBNetwork
- SCP-based image deployment
- Kindle power management reverse engineering

---

# Raspberry Pi OS / WiFi Issues

Initial Raspberry Pi OS installations caused major WiFi issues on the Raspberry Pi Zero W.

Symptoms included:

- `wlan0` remaining DOWN
- `rfkill` soft blocks
- `raspi-config` wireless setup failing
- `There was an error running option S1 Wireless LAN`
- DHCP failures
- unreliable WLAN behavior

Modern Raspberry Pi OS releases did not behave reliably on this hardware.

## Solution

Using:

- Raspberry Pi OS Lite
- Legacy / Bullseye release

resolved the WiFi problems completely.

This became the stable base system for the project.

---

# Kindle USBNetwork Troubleshooting

Initially the Kindle DX appeared only as a USB mass storage device.

The USBNetwork hack was installed successfully, but networking did not immediately work.

Important findings:

- Kindle exposes a USB Ethernet gadget interface (`usb0`)
- Static IP configuration was required
- Manual network setup was required on the Raspberry Pi side

Working configuration:

```text
Host (RPi3):    192.168.2.1
Kindle DX:      192.168.2.2
```

Commands used:

```bash
sudo ip addr add 192.168.2.1/24 dev usb0
sudo ip link set usb0 up
```

Connectivity test:

```bash
ping 192.168.2.2
```

Eventually the Kindle became reachable over SSH.

---

# Kindle SSH Access

SSH access was enabled through the USBNetwork package.

The Kindle runs:

```text
dropbear_2015.68
```

and exposes SSH over the USB Ethernet interface.

Successful login:

```bash
ssh root@192.168.2.2
```

Default root password:

```text
mario
```

---

# Kindle Root Filesystem

The Kindle root filesystem is mounted read-only by default.

To temporarily enable write access:

```bash
mntroot rw
```

To restore read-only mode:

```bash
mntroot ro
```

This was required when modifying SSH configuration and authentication files.

---

# Dropbear Public Key Authentication Problems

Public key authentication initially failed despite:

- correct SSH keys
- correct permissions
- correct `.ssh` directories

Several standard Linux locations were tested unsuccessfully:

```text
/root/.ssh/authorized_keys
/tmp/root/.ssh/authorized_keys
```

The reason was eventually discovered through binary inspection:

```bash
strings /usr/bin/dropbear | grep authorized
```

This revealed the actual path used by the Kindle USBNetwork environment:

```text
/mnt/us/usbnet/etc/authorized_keys
```

After placing the public key there:

```bash
cp authorized_keys /mnt/us/usbnet/etc/authorized_keys
chmod 600 /mnt/us/usbnet/etc/authorized_keys
```

passwordless SSH authentication finally worked.

---

# Kindle Power Management Reverse Engineering

The Kindle uses Amazon Lab126 proprietary power management components.

Important components:

```text
com.lab126.powerd
```

and:

```text
/usr/bin/powerd_test
```

The following command exposed available power management properties:

```bash
lipc-probe -v com.lab126.powerd
```

Important states discovered:

## Home / active state

```text
Powerd state: Active
```

## Screensaver state

```text
Powerd state: Screen Saver
```

This allowed the Raspberry Pi automation script to determine the current Kindle state before triggering refresh events.

---

# Discovering Programmatic Power Button Events

The hidden utility:

```text
/usr/bin/powerd_test
```

was discovered on the Kindle.

Running:

```bash
powerd_test -p
```

simulates a physical Kindle power button press.

This became the key component enabling fully automated dashboard refreshes.

---

# Screensaver Refresh Behavior

A major discovery was that the Kindle DX firmware does not reload the currently active screensaver image automatically.

Simply overwriting the image file does NOT refresh the displayed dashboard.

The Kindle only reloads screensaver images during a screensaver state transition.

## Resulting behavior

When the Kindle is already displaying the dashboard screensaver:

```text
screensaver -> wake -> screensaver
```

must be performed to force image reload.

This behavior appears to be related to proprietary Lab126 framework caching and e-paper refresh handling.

---

# Fully Automated Refresh Workflow

Final working refresh pipeline:

1. Raspberry Pi generates dashboard image with Python/Pillow
2. Image is transferred through SCP
3. Kindle power state is checked through `lipc`
4. Appropriate power button events are triggered automatically

The refresh process is fully automated over SSH.

---

# Interesting Kindle System Details

Kernel:

```text
Linux kindle 2.6.22.19-lab126 #3 PREEMPT Tue Jun 8 19:03:49 PDT 2010 armv6l unknown
```

Firmware:

```text
System Software Version: 008-TN2.1-049546
```

Interesting mountpoints:

```text
fsp on /opt/amazon/screen_saver/824x1200
fsp on /mnt/us
```

These appear directly related to Kindle framework screensaver handling.

---

# Lessons Learned

This project required significantly more reverse engineering and troubleshooting than initially expected.

Important lessons included:

- modern Linux assumptions often fail on old embedded devices
- proprietary framework behavior must often be experimentally discovered
- debugging old Dropbear/OpenSSH interoperability can be difficult
- e-paper refresh behavior may depend on hidden framework state transitions
- reverse engineering existing embedded utilities can be more effective than replacing them

The final result is a fully automated e-paper infrastructure dashboard running on repurposed Kindle hardware.

---

# Kindle Reverted to USB Drive Mode

At one point the Kindle unexpectedly reverted to USB Drive Mode instead of appearing as a USB Ethernet gadget.

Symptoms on the Raspberry Pi Zero W:

```text
No usb0 interface
Kindle appears as USB mass storage
/dev/sda1 appears
USB Drive Mode shown on Kindle screen
```

`dmesg` showed:

```text
usb-storage
sda: sda1
```

The USBNetwork hack was still installed, but automatic USB networking had been disabled.

The key file was:

```text
/mnt/us/usbnet/DISABLED_auto
```

The USBNetwork package documentation explains that renaming this file enables USB Ethernet mode by default.

Fix:

```bash
sudo mount /dev/sda1 /mnt/kindle
sudo mv /mnt/kindle/usbnet/DISABLED_auto /mnt/kindle/usbnet/auto
sync
sudo umount /mnt/kindle
```

Then reboot the Kindle and reconnect USB.

Expected result:

```text
Linux-USB Ethernet/RNDIS Gadget
usb0
```

After this, the Pi Zero W can configure the USB Ethernet link again:

```bash
sudo ip addr add 192.168.2.1/24 dev usb0
ping -c 3 192.168.2.2
```

Successful SSH test:

```bash
ssh -i ~/.ssh/id_rsa root@192.168.2.2
```

This issue is now documented because it can look like a broken USBNetwork installation, even though the fix is only restoring the `auto` marker file.
