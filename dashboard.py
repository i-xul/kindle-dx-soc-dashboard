from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# ----------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------

import psutil
import shutil
import subprocess
import os
import socket
import re
import hashlib
import json

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

SERVER = "hmasi@192.168.1.111"
STATE_FILE = "/home/hmasi/kindle-dashboard/.dashboard_state.json"

WIDTH = 824
HEIGHT = 1200

# ----------------------------------------------------------------------
# Canvas and fonts
# ----------------------------------------------------------------------

img = Image.new("L", (WIDTH, HEIGHT), 255)
draw = ImageDraw.Draw(img)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
font_title = ImageFont.truetype(FONT, 40)
font_section = ImageFont.truetype(FONT, 30)
font_text = ImageFont.truetype(FONT, 25)
font_small = ImageFont.truetype(FONT, 20)

# ----------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------

def text(x, y, value, font=font_text):
    draw.text((x, y), value, font=font, fill=0)

def line(y):
    draw.line((35, y, WIDTH - 35, y), fill=0, width=2)

def box(x1, y1, x2, y2):
    draw.rectangle((x1, y1, x2, y2), outline=0, width=2)

# ----------------------------------------------------------------------
# Local system data
# ----------------------------------------------------------------------

def get_cpu_temp():
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"]).decode().strip()
        return out.replace("temp=", "")
    except Exception:
        return "N/A"

def get_uptime():
    seconds = int(float(open("/proc/uptime").read().split()[0]))
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"

def get_ip():
    try:
        return subprocess.check_output(
            "hostname -I | awk '{print $1}'",
            shell=True
        ).decode().strip()
    except Exception:
        return "N/A"

# ----------------------------------------------------------------------
# Remote infrastructure and security data
# ----------------------------------------------------------------------

def get_fail2ban_status():
    try:
        output = subprocess.check_output(
            [
                "ssh",
                SERVER,
                "sudo -n fail2ban-client status"
            ],
            timeout=10
        ).decode()

        jail_match = re.search(r"Jail list:\s*(.*)", output)

        if jail_match:
            jails = [j.strip() for j in jail_match.group(1).split(",")]

            total_banned = 0
            banned_ips = []
            jail_ban_counts = {}

            for jail in jails:
                jail_output = subprocess.check_output(
                    [
                        "ssh",
                        SERVER,
                        f"sudo -n fail2ban-client status {jail}"
                    ],
                    timeout=10
                ).decode()

                banned_match = re.search(r"Currently banned:\s*(\d+)", jail_output)

                if banned_match:
                    banned_count = int(banned_match.group(1))
                    total_banned += banned_count
                    jail_ban_counts[jail] = banned_count

                ip_match = re.search(r"Banned IP list:\s*(.*)", jail_output)

                if ip_match:
                    ips = ip_match.group(1).split()
                    banned_ips.extend(ips)

            latest_ip = banned_ips[-1] if banned_ips else "none"

            top_jail = "none"
            if jail_ban_counts:
                top_jail = max(jail_ban_counts, key=jail_ban_counts.get)

            return (
                f"{len(jails)} jails",
                f"{total_banned} banned",
                latest_ip,
                top_jail
            )

    except Exception as e:
        return ("Unavailable", "Unavailable", str(e)[:30], "Unavailable")

    return ("Unavailable", "Unavailable", "Unavailable", "Unavailable")

def get_docker_status():
    try:
        output = subprocess.check_output(
            [
                "ssh",
                SERVER,
                "docker ps --format '{{.Names}}'"
            ],
            timeout=10
        ).decode()

        containers = [
            line.strip()
            for line in output.splitlines()
            if line.strip()
        ]

        count = len(containers)

        unhealthy_output = subprocess.check_output(
            [
                "ssh",
                SERVER,
                "docker ps --filter health=unhealthy --format '{{.Names}}'"
            ],
            timeout=10
        ).decode()

        unhealthy = [
            line.strip()
            for line in unhealthy_output.splitlines()
            if line.strip()
        ]

        if unhealthy:
            return (
                f"{count} running",
                f"UNHEALTHY: {unhealthy[0]}"
            )

        return (
            f"{count} running",
            "All healthy"
        )

    except Exception as e:
        return (
            "Unavailable",
            str(e)[:30]
        )

def get_nginx_status():
    try:
        output = subprocess.check_output(
            ["ssh", SERVER, "systemctl is-active nginx"],
            timeout=10
        ).decode().strip()

        return output
    except Exception:
        return "Unavailable"

# ----------------------------------------------------------------------
# Security interpretation
# ----------------------------------------------------------------------

def get_security_status(suspicious_1h, suspicious_24h):
    try:
        one_hour = int(suspicious_1h)
        one_day = int(suspicious_24h)

        if one_hour >= 20:
            return "ACTIVE ATTACK"

        elif one_hour >= 5:
            return "ELEVATED"

        elif one_day >= 100:
            return "ELEVATED"

        else:
            return "NORMAL"

    except Exception:
        return "UNKNOWN"

def get_suspicious_time_counts():
    try:
        output = subprocess.check_output(
            [
                "ssh",
                SERVER,
                r"""python3 - <<'PY'
import re
from datetime import datetime, timedelta

log_file = "/var/log/nginx/access.log"
pattern = re.compile(r'wp-login|\.env|/admin|/phpmyadmin|/\.git|/xmlrpc', re.I)
time_pattern = re.compile(r'\[(.*?)\]')
ip_pattern = re.compile(r'^(\S+)')

now = datetime.now().astimezone()
one_hour_ago = now - timedelta(hours=1)
one_day_ago = now - timedelta(hours=24)

count_1h = 0
count_24h = 0
ips_1h = set()
ips_24h = set()

with open(log_file, "r", errors="ignore") as f:
    for line in f:
        if not pattern.search(line):
            continue

        time_match = time_pattern.search(line)
        ip_match = ip_pattern.search(line)

        if not time_match or not ip_match:
            continue

        try:
            ts = datetime.strptime(time_match.group(1), "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            continue

        ip = ip_match.group(1)

        if ts >= one_day_ago:
            count_24h += 1
            ips_24h.add(ip)

        if ts >= one_hour_ago:
            count_1h += 1
            ips_1h.add(ip)

print(f"{count_1h},{count_24h},{len(ips_1h)},{len(ips_24h)}")
PY"""
            ],
            timeout=10
        ).decode().strip()

        one_hour, one_day, unique_1h, unique_24h = output.split(",")
        return one_hour, one_day, unique_1h, unique_24h

    except Exception:
        return "N/A", "N/A", "N/A", "N/A"

def get_recent_attack_paths():
    try:
        output = subprocess.check_output(
            [
                "ssh",
                SERVER,
                r"""grep -Ei 'wp-login|\.env|/admin|/phpmyadmin|/\.git|/xmlrpc' /var/log/nginx/access.log | tail -3"""
            ],
            timeout=10
        ).decode()

        paths = []

        for line in output.splitlines():
            match = re.search(r'"[A-Z]+\s+([^ ]+)', line)

            if match:
                paths.append(match.group(1))

        paths = list(dict.fromkeys(paths))

        return paths[:3]

    except Exception:
        return ["Unavailable"]

def get_top_attacker_ip():
    try:
        output = subprocess.check_output(
            [
                "ssh",
                SERVER,
                r"""tail -5000 /var/log/nginx/access.log | grep -Ei 'wp-login|\.env|/admin|/phpmyadmin|/\.git|/xmlrpc' | awk '{print $1}' | sort | uniq -c | sort -nr | head -1"""
            ],
            timeout=10
        ).decode().strip()

        if not output:
            return "none"

        parts = output.split()
        if len(parts) >= 2:
            count = parts[0]
            ip = parts[1]
            return f"{ip} ({count} hits)"

        return "none"

    except Exception:
        return "Unavailable"

# ----------------------------------------------------------------------
# Dashboard state handling
# ----------------------------------------------------------------------

def load_dashboard_state():
    """Load previous dashboard data hash and timestamps.

    The state file lets the dashboard separate two concepts:
    - Upd: when monitored data last changed
    - Chk: when the dashboard last checked the system
    """
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_dashboard_state(state):
    """Persist dashboard state between refresh runs."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def build_data_fingerprint(data):
    """Create a stable hash from the monitored dashboard data.

    The current check timestamp is intentionally excluded so the hash only
    changes when real monitored data changes.
    """
    payload = json.dumps(data, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

# ----------------------------------------------------------------------
# Collect dashboard data
# ----------------------------------------------------------------------

# Collect current dashboard data from the local Pi Zero W and the monitored RPi 4.
# This data is also used to determine whether the visible dashboard content has changed.
now = datetime.now()
check_time = now.strftime("%d.%m.%Y %H:%M")

hostname = socket.gethostname()
ip = get_ip()

fail2ban_jails, fail2ban_banned, latest_banned_ip, top_fail2ban_jail = get_fail2ban_status()
docker_count, docker_health = get_docker_status()
recent_paths = get_recent_attack_paths()
top_attacker_ip = get_top_attacker_ip()
nginx_status = get_nginx_status()
suspicious_1h, suspicious_24h, unique_ips_1h, unique_ips_24h = get_suspicious_time_counts()

security_status = get_security_status(
    suspicious_1h,
    suspicious_24h
)

# Cat face reflects the current security status.
if security_status == "NORMAL":
    cat_face = "^.^"
elif security_status == "ELEVATED":
    cat_face = "o.o"
elif security_status == "ACTIVE ATTACK":
    cat_face = "O.O"
else:
    cat_face = "?.?"

load1, load5, load15 = os.getloadavg()
ram = psutil.virtual_memory()
disk = shutil.disk_usage("/")
disk_percent = disk.used / disk.total * 100

# Build a fingerprint from monitored values only.
# The check timestamp is excluded so unchanged data keeps the same update time.
dashboard_data = {
    "hostname": hostname,
    "ip": ip,
    "fail2ban_jails": fail2ban_jails,
    "fail2ban_banned": fail2ban_banned,
    "latest_banned_ip": latest_banned_ip,
    "top_fail2ban_jail": top_fail2ban_jail,
    "docker_count": docker_count,
    "docker_health": docker_health,
    "recent_paths": recent_paths,
    "top_attacker_ip": top_attacker_ip,
    "nginx_status": nginx_status,
    "suspicious_1h": suspicious_1h,
    "suspicious_24h": suspicious_24h,
    "unique_ips_1h": unique_ips_1h,
    "unique_ips_24h": unique_ips_24h,
    "security_status": security_status,
    "load1": round(load1, 2),
    "load5": round(load5, 2),
    "load15": round(load15, 2),
    "ram_percent": round(ram.percent, 1),
    "disk_percent": round(disk_percent, 1),
}

state = load_dashboard_state()
current_hash = build_data_fingerprint(dashboard_data)

if state.get("last_data_hash") != current_hash:
    update_time = check_time
    state["last_data_hash"] = current_hash
    state["last_update_time"] = update_time
else:
    update_time = state.get("last_update_time", check_time)

# Compare the current 1h suspicious request count with the previous run.
# The trend is intentionally simple and ASCII-only for Kindle/font reliability.
try:
    current_1h = int(suspicious_1h)
    previous_1h = int(state.get("previous_suspicious_1h", current_1h))

    if current_1h > previous_1h:
        attack_trend = "^"
    elif current_1h < previous_1h:
        attack_trend = "v"
    else:
        attack_trend = "="

    state["previous_suspicious_1h"] = current_1h

except Exception:
    attack_trend = "?"
    state["previous_suspicious_1h"] = suspicious_1h

state["last_check_time"] = check_time
save_dashboard_state(state)

# ----------------------------------------------------------------------
# Dashboard header
# ----------------------------------------------------------------------

# Header
text(35, 30, "Kindle SOC Dashboard", font_title)

# Dashboard timestamps
# Upd = last time monitored data changed
# Chk = last time the dashboard checked the monitored system
upd_text = f"Upd: {update_time[-5:]}"
chk_text = f"Chk: {check_time[-5:]}"

upd_bbox = draw.textbbox((0, 0), upd_text, font=font_small)
chk_bbox = draw.textbbox((0, 0), chk_text, font=font_small)

upd_width = upd_bbox[2] - upd_bbox[0]
chk_width = chk_bbox[2] - chk_bbox[0]

text(WIDTH - 35 - upd_width, 25, upd_text, font_small)
text(WIDTH - 35 - chk_width, 58, chk_text, font_small)

text(35, 95, "Zero W | RPi 4", font_small)
line(135)

# ----------------------------------------------------------------------
# System status section
# ----------------------------------------------------------------------

# System box
box(35, 160, 789, 435)
text(55, 180, "SYSTEM STATUS", font_section)

text(55, 235, f"CPU:  {get_cpu_temp()}")
text(55, 275, f"Load: {load1:.2f} / {load5:.2f} / {load15:.2f}")
text(55, 315, f"RAM:  {ram.percent:.1f}%")
text(55, 355, f"Disk: {disk_percent:.1f}%")
text(55, 395, f"Up:   {get_uptime()}")
text(620, 230, r" /\_/\ ", font_small)
text(615, 255, f"({cat_face})", font_small)
text(607, 280, r" > ^ < ", font_small)

# ----------------------------------------------------------------------
# Infrastructure section
# ----------------------------------------------------------------------

# Service box
box(35, 455, 789, 730)
text(55, 475, "INFRASTRUCTURE", font_section)

text(55, 530, f"Fail2ban:   {fail2ban_jails} / {fail2ban_banned}")
text(55, 570, f"Docker:     {docker_count}")
text(55, 610, f"Containers: {docker_health}")
text(55, 650, f"Nginx:      {nginx_status}")

# ----------------------------------------------------------------------
# Security snapshot section
# ----------------------------------------------------------------------

# Security box
box(35, 750, 789, 1145)
text(55, 770, "SECURITY SNAPSHOT", font_section)

text(55, 825, f"Status: {security_status}")
text(430, 825, f"Trend: {attack_trend}")

text(55, 870, f"1h: {suspicious_1h}")
text(430, 870, f"24h: {suspicious_24h}")

text(55, 910, f"IPs: {unique_ips_1h}")
text(430, 910, f"IPs: {unique_ips_24h}")

text(55, 955, f"Latest ban: {latest_banned_ip}")
text(55, 1000, f"Top IP:     {top_attacker_ip}")
text(55, 1045, f"Top jail:   {top_fail2ban_jail}")

paths_text = " | ".join(recent_paths)
text(55, 1090, "Recent:")
text(185, 1093, paths_text, font_small)

# Footer
# line(1170)
# text(35, 1178, "Generated by Raspberry Pi Zero W", font_small)

# ----------------------------------------------------------------------
# Save generated dashboard image
# ----------------------------------------------------------------------

img.save("dashboard.png")
print("dashboard.png generated")
