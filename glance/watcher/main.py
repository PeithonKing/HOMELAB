import psutil
import time
import os
import subprocess


FREQUENCY = 1  # seconds
MAX_LINES = 7 * 24 * 60 * 60 // FREQUENCY  # 1 week 
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "data")
COUNT_FILE = os.path.join(DATA_DIR, "count")

os.makedirs(DATA_DIR, exist_ok=True)

# Initialize count file if not exists
if not os.path.exists(COUNT_FILE):
    if os.path.exists(DATA_FILE):
        # Use wc -l to get line count
        result = subprocess.run(["wc", "-l", DATA_FILE], capture_output=True, text=True)
        count = int(result.stdout.strip().split()[0])
    else:
        count = 0
    with open(COUNT_FILE, "w") as f:
        f.write(f"{count}")

prev_net = None
while True:
    timestamp = int(time.time())
    cpu = psutil.cpu_percent(interval=None)
    mem_gb = psutil.virtual_memory().used / (1024 ** 3)  # memory in GB
    net = psutil.net_io_counters(pernic=True).get("wlan0")
    if not prev_net:
        prev_net = net
        continue

    time.sleep(FREQUENCY)
    upload_kbps = ((net.bytes_sent - prev_net.bytes_sent)) / (1024 * FREQUENCY)
    download_kbps = ((net.bytes_recv - prev_net.bytes_recv)) / (1024 * FREQUENCY)

    line = f"{timestamp}\t{cpu:.2f}\t{upload_kbps:.2f}\t{download_kbps:.2f}\t{mem_gb:.3f}\n"
    with open(DATA_FILE, "a") as f:
        f.write(line)
        print(line.strip())
    # Read count
    with open(COUNT_FILE) as f:
        count = int(f.read().strip())
    if count >= MAX_LINES:
        subprocess.run(["sed", "-i", "1d", DATA_FILE])
    else:
        with open(COUNT_FILE, "w") as f:
            f.write(f"{count + 1}\n")
    prev_net = net
