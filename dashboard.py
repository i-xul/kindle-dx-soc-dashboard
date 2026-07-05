#!/usr/bin/env python3
#
# ----------------------------------------------------------------------
# Kindle DX SOC Dashboard
# ----------------------------------------------------------------------
#
# Author: H A (i-xul)
# Repository: https://github.com/i-xul/kindle-dx-soc-dashboard
#
# Created: 2026-05-19
# Version: v1.0.0
#
# Description:
# Generates a Kindle DX security dashboard using Raspberry Pi based
# infrastructure monitoring data.
#
# Version history:
# v1.0.0 - Initial public release
#
# ----------------------------------------------------------------------

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

def get_remote_dashboard_data():
    """
    Collect all monitored infrastructure data with a single SSH connection.

    Keeping all remote data collection in one place minimizes connection
    overhead and provides a clean separation between data collection and
    dashboard rendering.
    """

    try:
        output = subprocess.check_output(
            [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=10",
                SERVER,
                r"""python3 - <<'PY'
import json
import re
import subprocess
from datetime import datetime, timedelta

log_file = "/var/log/nginx/access.log"
pattern = re.compile(r'wp-login|\.env|/admin|/phpmyadmin|/\.git|/xmlrpc', re.I)
time_pattern = re.compile(r'\[(.*?)\]')
ip_pattern = re.compile(r'^(\S+)')

data = {}

# Fail2ban
try:
    status = subprocess.check_output(
        ["sudo", "-n", "fail2ban-client", "status"],
        timeout=10
    ).decode()

    jail_match = re.search(r"Jail list:\s*(.*)", status)
    jails = [j.strip() for j in jail_match.group(1).split(",")] if jail_match else []

    total_banned = 0
    banned_ips = []
    jail_ban_counts = {}

    for jail in jails:
        jail_output = subprocess.check_output(
            ["sudo", "-n", "fail2ban-client", "status", jail],
            timeout=10
        ).decode()

        banned_match = re.search(r"Currently banned:\s*(\d+)", jail_output)
        banned_count = int(banned_match.group(1)) if banned_match else 0
        total_banned += banned_count
        jail_ban_counts[jail] = banned_count

        ip_match = re.search(r"Banned IP list:\s*(.*)", jail_output)
        if ip_match:
            banned_ips.extend(ip_match.group(1).split())

    data["fail2ban_jails"] = f"{len(jails)} jails"
    data["fail2ban_banned"] = f"{total_banned} banned"
    data["latest_banned_ip"] = banned_ips[-1] if banned_ips else "none"
    data["top_fail2ban_jail"] = max(jail_ban_counts, key=jail_ban_counts.get) if jail_ban_counts else "none"

except Exception as e:
    data["fail2ban_jails"] = "Unavailable"
    data["fail2ban_banned"] = "Unavailable"
    data["latest_banned_ip"] = str(e)[:30]
    data["top_fail2ban_jail"] = "Unavailable"

# Docker
try:
    containers = subprocess.check_output(
        ["docker", "ps", "--format", "{{.Names}}"],
        timeout=10
    ).decode().splitlines()

    unhealthy = subprocess.check_output(
        ["docker", "ps", "--filter", "health=unhealthy", "--format", "{{.Names}}"],
        timeout=10
    ).decode().splitlines()

    data["docker_count"] = f"{len([c for c in containers if c.strip()])} running"
    data["docker_health"] = f"UNHEALTHY: {unhealthy[0]}" if unhealthy else "All healthy"

except Exception as e:
    data["docker_count"] = "Unavailable"
    data["docker_health"] = str(e)[:30]

# Nginx
try:
    data["nginx_status"] = subprocess.check_output(
        ["systemctl", "is-active", "nginx"],
        timeout=10
    ).decode().strip()
except Exception:
    data["nginx_status"] = "Unavailable"

# Nginx suspicious activity
try:
    now = datetime.now().astimezone()
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(hours=24)

    count_1h = 0
    count_24h = 0
    ips_1h = set()
    ips_24h = set()
    recent_paths = []
    top_ip_counts = {}

    with open(log_file, "r", errors="ignore") as f:
        lines = f.readlines()[-10000:]

    for line in lines:
        if not pattern.search(line):
            continue

        time_match = time_pattern.search(line)
        ip_match = ip_pattern.search(line)
        path_match = re.search(r'"[A-Z]+\s+([^ ]+)', line)

        if path_match:
            recent_paths.append(path_match.group(1))

        if ip_match:
            ip = ip_match.group(1)
            top_ip_counts[ip] = top_ip_counts.get(ip, 0) + 1

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

    data["suspicious_1h"] = str(count_1h)
    data["suspicious_24h"] = str(count_24h)
    data["unique_ips_1h"] = str(len(ips_1h))
    data["unique_ips_24h"] = str(len(ips_24h))
    data["recent_paths"] = list(dict.fromkeys(recent_paths[-3:]))

    if top_ip_counts:
        top_ip = max(top_ip_counts, key=top_ip_counts.get)
        data["top_attacker_ip"] = f"{top_ip} ({top_ip_counts[top_ip]} hits)"
    else:
        data["top_attacker_ip"] = "none"

except Exception:
    data["suspicious_1h"] = "N/A"
    data["suspicious_24h"] = "N/A"
    data["unique_ips_1h"] = "N/A"
    data["unique_ips_24h"] = "N/A"
    data["recent_paths"] = ["Unavailable"]
    data["top_attacker_ip"] = "Unavailable"

print(json.dumps(data))
PY"""
            ],
            timeout=30
        ).decode().strip()

        return json.loads(output)

    except Exception:
        return {}

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

def get_attack_activity(suspicious_1h, unique_ips_1h, attack_trend):
    """Summarize current attack activity in a short SOC-style label."""
    try:
        one_hour = int(suspicious_1h)
        unique_ips = int(unique_ips_1h)

        if one_hour >= 20 or unique_ips >= 10:
            return "Heavy probing"

        if one_hour >= 5 or unique_ips >= 3 or attack_trend == "^":
            return "Scanning"

        return "Quiet"

    except Exception:
        return "Unknown"

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

remote_data = get_remote_dashboard_data()

fail2ban_jails = remote_data.get("fail2ban_jails", "Unavailable")
fail2ban_banned = remote_data.get("fail2ban_banned", "Unavailable")
latest_banned_ip = remote_data.get("latest_banned_ip", "Unavailable")
top_fail2ban_jail = remote_data.get("top_fail2ban_jail", "Unavailable")

docker_count = remote_data.get("docker_count", "Unavailable")
docker_health = remote_data.get("docker_health", "Unavailable")
nginx_status = remote_data.get("nginx_status", "Unavailable")

recent_paths = remote_data.get("recent_paths", ["Unavailable"])
top_attacker_ip = remote_data.get("top_attacker_ip", "Unavailable")

suspicious_1h = remote_data.get("suspicious_1h", "N/A")
suspicious_24h = remote_data.get("suspicious_24h", "N/A")
unique_ips_1h = remote_data.get("unique_ips_1h", "N/A")
unique_ips_24h = remote_data.get("unique_ips_24h", "N/A")

security_status = get_security_status(
    suspicious_1h,
    suspicious_24h
)

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
    # "attack_activity": attack_activity,
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

    change = current_1h - previous_1h

    if change >= 2:
        attack_trend = "^"
    elif change <= -2:
        attack_trend = "v"
    else:
        attack_trend = "="

    state["previous_suspicious_1h"] = current_1h

except Exception:
    attack_trend = "?"
    state["previous_suspicious_1h"] = suspicious_1h

attack_activity = get_attack_activity(
    suspicious_1h,
    unique_ips_1h,
    attack_trend
)

# ----------------------------------------------------------------------
# SOC cat
#
# The cat provides a quick visual summary of the current security posture.
# It reacts to the overall security status, attack trend and activity level.
# ----------------------------------------------------------------------

if security_status == "ACTIVE ATTACK":
    if attack_trend == "^":
        cat_face = ">.<"
    elif attack_trend == "v":
        cat_face = "o.o"
    else:
        cat_face = "O.O"

elif security_status == "ELEVATED":
    if attack_trend == "^":
        cat_face = "O.O"
    elif attack_trend == "v":
        cat_face = "-.-"
    else:
        cat_face = "o.o"

else:
    if attack_activity == "Scanning":
        cat_face = "o.o"
    else:
        cat_face = "^.^"

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
text(500, 825, f"Trend: {attack_trend}")
text(55, 870, f"Activity: {attack_activity}")

text(500, 870, f"1h: {suspicious_1h}")
text(500, 915, f"24h: {suspicious_24h}")

text(500, 960, f"IPs 1h: {unique_ips_1h}")
text(500, 1005, f"IPs 24h: {unique_ips_24h}")

text(55, 915, f"Latest ban: {latest_banned_ip}")
text(55, 960, f"Top IP:     {top_attacker_ip}")
text(55, 1005, f"Top jail:   {top_fail2ban_jail}")

paths_text = " | ".join(recent_paths)
text(55, 1050, "Recent:")
text(185, 1053, paths_text, font_small)

# ----------------------------------------------------------------------
# Footer
# ----------------------------------------------------------------------

# line(1170)

text(35, 1175, "Kindle DX SOC Dashboard", font_small)
text(WIDTH - 120, 1175, "v1.0.0", font_small)

# ----------------------------------------------------------------------
# Save generated dashboard image
# ----------------------------------------------------------------------

img.save("dashboard.png")
print("dashboard.png generated")
