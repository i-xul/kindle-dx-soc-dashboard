from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import psutil
import shutil
import subprocess
import os
import socket
import re

SERVER = "hmasi@192.168.1.111"

WIDTH = 824
HEIGHT = 1200

img = Image.new("L", (WIDTH, HEIGHT), 255)
draw = ImageDraw.Draw(img)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
font_title = ImageFont.truetype(FONT, 40)
font_section = ImageFont.truetype(FONT, 30)
font_text = ImageFont.truetype(FONT, 25)
font_small = ImageFont.truetype(FONT, 20)

def text(x, y, value, font=font_text):
    draw.text((x, y), value, font=font, fill=0)

def line(y):
    draw.line((35, y, WIDTH - 35, y), fill=0, width=2)

def box(x1, y1, x2, y2):
    draw.rectangle((x1, y1, x2, y2), outline=0, width=2)

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


def get_security_log_status():
    try:
        output = subprocess.check_output(
            [
                "ssh",
                SERVER,
                r"""tail -1000 /var/log/nginx/access.log | grep -Eic 'wp-login|\.env|/admin|/phpmyadmin|/\.git|/xmlrpc'"""
            ],
            timeout=10
        ).decode().strip()

        return f"{output} suspicious / last 1000"
    except Exception:
        return "Unavailable"

def get_security_status(security_log_status):
    try:
        suspicious_count = int(security_log_status.split()[0])

        if suspicious_count >= 500:
            return "ACTIVE ATTACK"
        elif suspicious_count >= 100:
            return "ELEVATED"
        else:
            return "NORMAL"

    except Exception:
        return "UNKNOWN"

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

now = datetime.now()
hostname = socket.gethostname()
ip = get_ip()
fail2ban_jails, fail2ban_banned, latest_banned_ip, top_fail2ban_jail  = get_fail2ban_status()
docker_count, docker_health = get_docker_status()
recent_paths = get_recent_attack_paths()
top_attacker_ip = get_top_attacker_ip()
nginx_status = get_nginx_status()
security_log_status = get_security_log_status()
security_status = get_security_status(security_log_status)

load1, load5, load15 = os.getloadavg()
ram = psutil.virtual_memory()
disk = shutil.disk_usage("/")
disk_percent = disk.used / disk.total * 100

# Header
text(35, 30, "Kindle SOC Dashboard", font_title)

upd_text = now.strftime("Upd: %d.%m.%Y %H:%M")
upd_bbox = draw.textbbox((0, 0), upd_text, font=font_small)
upd_width = upd_bbox[2] - upd_bbox[0]
text(WIDTH - 35 - upd_width, 42, upd_text, font_small)

text(35, 95, "Zero W | RPi 4", font_small)
line(135)

# System box
box(35, 160, 789, 435)
text(55, 180, "SYSTEM STATUS", font_section)

text(55, 235, f"CPU:  {get_cpu_temp()}")
text(55, 275, f"Load: {load1:.2f} / {load5:.2f} / {load15:.2f}")
text(55, 315, f"RAM:  {ram.percent:.1f}%")
text(55, 355, f"Disk: {disk_percent:.1f}%")
text(55, 395, f"Up:   {get_uptime()}")

# Service box
box(35, 455, 789, 730)
text(55, 475, "INFRASTRUCTURE", font_section)

text(55, 530, f"Fail2ban:   {fail2ban_jails} / {fail2ban_banned}")
text(55, 570, f"Docker:     {docker_count}")
text(55, 610, f"Containers: {docker_health}")
text(55, 650, f"Nginx:      {nginx_status}")
text(55, 690, f"Security:   {security_log_status}")

# Security box
box(35, 750, 789, 1048)
text(55, 770, "SECURITY SNAPSHOT", font_section)

text(55, 825, f"Status: {security_status}")
text(55, 870, f"Latest banned IP:      {latest_banned_ip}")
text(55, 915, f"Top attacker IP:       {top_attacker_ip}")
text(55, 960, f"Top Fail2ban jail:     {top_fail2ban_jail}")
paths_text = " | ".join(recent_paths)

text(55, 1005, "Recent attack paths:")

paths_text = " | ".join(recent_paths)

text(340, 1008, paths_text, font_small)

# Footer
# line(1170)
# text(35, 1178, "Generated by Raspberry Pi 3", font_small)

img.save("dashboard.png")
print("dashboard.png generated")
