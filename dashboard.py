from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import psutil
import shutil
import subprocess
import os
import socket
import re

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
                "hmasi@192.168.1.11",
                "sudo -n fail2ban-client status"
            ],
            timeout=10
        ).decode()

        jail_match = re.search(r"Jail list:\s*(.*)", output)

        if jail_match:
            jails = [j.strip() for j in jail_match.group(1).split(",")]

            total_banned = 0
            banned_ips = []

            for jail in jails:
                jail_output = subprocess.check_output(
                    [
                        "ssh",
                        "hmasi@192.168.1.11",
                        f"sudo -n fail2ban-client status {jail}"
                    ],
                    timeout=10
                ).decode()

                banned_match = re.search(r"Currently banned:\s*(\d+)", jail_output)

                if banned_match:
                    total_banned += int(banned_match.group(1))

                ip_match = re.search(r"Banned IP list:\s*(.*)", jail_output)

                if ip_match:
                    ips = ip_match.group(1).split()
                    banned_ips.extend(ips)

            latest_ip = banned_ips[-1] if banned_ips else "none"


            return (
                f"{len(jails)} jails",
                f"{total_banned} banned",
                latest_ip
            )

    except Exception as e:
        return ("Unavailable", "Unavailable", str(e)[:30])

    return ("Unavailable", "Unavailable", "Unavailable")

def get_docker_status():
    try:
        output = subprocess.check_output(
            [
                "ssh",
                "hmasi@192.168.1.11",
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
                "hmasi@192.168.1.11",
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

def get_recent_attack_paths():
    try:
        output = subprocess.check_output(
            [
                "ssh",
                "hmasi@192.168.1.11",
                r"""grep -Ei 'wp-login|\.env|/admin|/phpmyadmin|/\.git|/xmlrpc' /var/log/nginx/access.log | tail -3"""
            ],
            timeout=10
        ).decode()

        paths = []

        for line in output.splitlines():
            match = re.search(r'"[A-Z]+\s+([^ ]+)', line)

            if match:
                paths.append(match.group(1))

        return paths[:3]

    except Exception:
        return ["Unavailable"]

now = datetime.now()
hostname = socket.gethostname()
ip = get_ip()
fail2ban_jails, fail2ban_banned, latest_banned_ip  = get_fail2ban_status()
docker_count, docker_health = get_docker_status()
recent_paths = get_recent_attack_paths()

load1, load5, load15 = os.getloadavg()
ram = psutil.virtual_memory()
disk = shutil.disk_usage("/")
disk_percent = disk.used / disk.total * 100

# Header
text(35, 30, "Kindle SOC Dashboard", font_title)
text(35, 85, now.strftime("%A %d.%m.%Y  %H:%M"), font_text)
text(35, 125, f"Node: {hostname}  |  IP: {ip}", font_small)
line(165)

# System box
box(35, 195, 789, 520)
text(55, 215, "SYSTEM STATUS", font_section)

text(55, 275, f"CPU temperature: {get_cpu_temp()}")
text(55, 325, f"Load average:    {load1:.2f} / {load5:.2f} / {load15:.2f}")
text(55, 375, f"RAM usage:       {ram.percent:.1f}%")
text(55, 425, f"Disk usage:      {disk_percent:.1f}%")
text(55, 475, f"Uptime:          {get_uptime()}")

# Service box
box(35, 535, 789, 910)
text(55, 555, "INFRASTRUCTURE", font_section)

text(55, 615, f"Fail2ban:        {fail2ban_jails} / {fail2ban_banned}")
text(55, 665, f"Docker:          {docker_count}")
text(55, 715, f"Container state: {docker_health}")
text(55, 765, "Nginx:           pending remote data")
text(55, 815, "Security logs:   pending remote data")

# Security box
box(35, 940, 789, 1180)
text(55, 960, "SECURITY SNAPSHOT", font_section)

text(55, 1010, f"Latest banned IP:      {latest_banned_ip}")
text(55, 1060, "Recent attack paths:")

y = 1100

for path in recent_paths:
    text(75, y, path, font_small)
    y += 30

text(55, 1110, "Banned IPs:            pending")

# Footer
line(1190)
text(35, 1210, "Generated by Raspberry Pi 3", font_small)

img.save("dashboard.png")
print("dashboard.png generated")
