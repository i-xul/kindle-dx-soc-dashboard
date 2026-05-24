# Kindle Dashboard systemd Timer

The Kindle dashboard refresh process is automated through a user-level systemd timer on the Raspberry Pi 3.

---

# Service Unit

Location:

```text
~/.config/systemd/user/kindle-dashboard.service
```

Contents:

```ini
[Unit]
Description=Kindle Dashboard Refresh

[Service]
Type=oneshot
WorkingDirectory=/home/hmasi/kindle-dashboard
ExecStart=/home/hmasi/kindle-dashboard/scripts/update_dashboard.sh
```

---

# Timer Unit

Location:

```text
~/.config/systemd/user/kindle-dashboard.timer
```

Contents:

```ini
[Unit]
Description=Run Kindle Dashboard Refresh every 15 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
```

---

# Enable Timer

```bash
systemctl --user daemon-reload
systemctl --user enable --now kindle-dashboard.timer
```

---

# Check Status

```bash
systemctl --user status kindle-dashboard.timer
```

List timers:

```bash
systemctl --user list-timers
```

---

# Refresh Workflow

The timer automatically triggers:

```text
update_dashboard.sh
```

which:

1. Generates a fresh dashboard image
2. Transfers the image to the Kindle DX over SCP
3. Detects Kindle power state through `lipc`
4. Performs the required power state transitions through `powerd_test`

---

# Important Kindle Behavior

The Kindle DX only reloads screensaver images during a screensaver state transition.

If the device is already in screensaver mode, the refresh workflow performs:

```text
screensaver -> wake -> screensaver
```

to force the Kindle framework to reload the updated image.
