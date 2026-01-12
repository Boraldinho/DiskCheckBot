import subprocess
import requests
import os
from dotenv import load_dotenv  # Добавить это

load_dotenv()  # И это (загружает данные из .env)
# --- НАСТРОЙКИ (БЕЗОПАСНЫЕ) ---
# Скрипт будет искать эти данные в переменных окружения вашего сервера
TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

# Список серверов (IP можно оставить, если они локальные)
SERVERS = [
    {
        "host": "root@192.168.90.160",
        "alias": "VABitrix",
        "disks": ["sdb", "sdc", "sdd", "sde", "sdf"]
    },
    {
        "host": "root@192.168.90.240",
        "alias": "VA1",
        "disks": ["nvme0n1", "nvme1n1"]
    }
]

CRITICAL_WEAR = 90
MAX_HDD_HOURS = 50000
# ------------------------------

def send_tg(message):
    if not TOKEN or not CHAT_ID:
        print("Ошибка: Не установлены переменные окружения TG_BOT_TOKEN или TG_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=20)
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")

final_report = []

for server in SERVERS:
    host = server["host"]
    alias = server["alias"]
    ip = host.split('@')[-1]
    
    server_report = [f"<b>Сервер {ip} - {alias}</b>\n<b>Диски:</b>"]
    
    for dev in server["disks"]:
        try:
            # 1. Получаем размер диска
            size_cmd = f"ssh {host} lsblk -dn -o SIZE /dev/{dev}"
            disk_size = subprocess.check_output(size_cmd, shell=True).decode().strip()

            # 2. Получаем данные SMART
            flag = "-a" if "nvme" in dev else "-A"
            ssh_cmd = f"ssh {host} /usr/sbin/smartctl {flag} /dev/{dev}"
            res = subprocess.check_output(ssh_cmd, shell=True).decode()
            
            wear_percent = None
            hours = 0
            reallocated = 0
            temp = "?? "
            
            for line in res.splitlines():
                if "Percentage Used:" in line:
                    wear_percent = int(line.split(":")[1].strip().replace("%", ""))
                if "Wear_Leveling_Count" in line:
                    wear_percent = 100 - int(line.split()[3])
                if "Power_On_Hours" in line:
                    hours = int(line.replace(",", "").split()[-1])
                if "Reallocated_Sector_Ct" in line:
                    reallocated = int(line.split()[-1])
                if "Temperature" in line:
                    temp = line.split()[-1]

            # Формирование строки
            if "nvme" in dev:
                status = f"• {dev} ({disk_size}, NVMe) - {wear_percent}% износа"
            elif wear_percent is not None:
                if wear_percent >= CRITICAL_WEAR:
                    status = f"🔴 <b>{dev} ({disk_size}, SSD) - {wear_percent}% износа!</b>"
                else:
                    status = f"• {dev} ({disk_size}, SSD) - {wear_percent}% износа"
            else:
                if reallocated > 0:
                    status = f"🔴 <b>{dev} ({disk_size}, HDD) - {reallocated} БИТЫХ СЕКТОРОВ!</b>"
                elif hours > MAX_HDD_HOURS:
                    status = f"⚠️ <b>{dev} ({disk_size}, HDD) - {hours} ч.</b> (Старый) | {temp}°C"
                else:
                    status = f"• {dev} ({disk_size}, HDD) - {hours} ч. | {temp}°C"
            
            server_report.append(status)

        except Exception:
            server_report.append(f"❌ {dev} - ошибка доступа")
    
    final_report.append("\n".join(server_report))

if final_report:
    send_tg("\n\n" + "\n\n---\n\n".join(final_report))