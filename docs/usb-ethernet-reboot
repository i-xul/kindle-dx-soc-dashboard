# Kindle USB Ethernet After Reboot

The Kindle DX dashboard uses USB Ethernet between the Raspberry Pi and the Kindle.

After a Raspberry Pi reboot, the `usb0` interface may exist but does not automatically have the required static IP configuration.

Required host-side configuration:

```text
RPi3 usb0: 192.168.2.1/24
Kindle:    192.168.2.2
```

Manual commands:

```bash
sudo ip link set usb0 up
sudo ip addr add 192.168.2.1/24 dev usb0
```

To make this persistent, a small systemd service can be used.

## systemd service

```ini
[Unit]
Description=Configure Kindle USB Ethernet interface
After=network.target
Wants=network.target

[Service]
Type=oneshot
ExecStart=/sbin/ip link set usb0 up
ExecStart=/sbin/ip addr add 192.168.2.1/24 dev usb0
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

Verify:

```bash
ip a show usb0
ping -c 3 192.168.2.2
```

This makes the SSH/SCP dashboard refresh workflow survive Raspberry Pi reboots more reliably.
