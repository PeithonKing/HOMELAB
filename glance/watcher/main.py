# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psutil==5.9.5",
#     "SQLAlchemy==2.0.29",
# ]
# ///

import psutil
import time
import os
from sqlalchemy import create_engine, Column, Integer, Float
from sqlalchemy.orm import declarative_base, sessionmaker

FREQUENCY = 1
MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 1 week
DB_FILE = os.path.join("stats.db")


engine = create_engine(f"sqlite:///{DB_FILE}")
Base = declarative_base()

class Stat(Base):
    __tablename__ = "stats"
    timestamp = Column(Integer, primary_key=True)
    cpu = Column(Float)
    upload_kbps = Column(Float)
    download_kbps = Column(Float)
    mem_gb = Column(Float)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

prev_net = None
loop_count = 0

print("Watcher started with uv and SQLAlchemy!")

while True:
    timestamp = int(time.time())
    cpu = psutil.cpu_percent(interval=None)
    mem_gb = psutil.virtual_memory().used / (1024 ** 3)
    
    net_counters = psutil.net_io_counters(pernic=True)
    net = net_counters.get("wlan0")
    
    if not net:
        time.sleep(FREQUENCY)
        continue

    if not prev_net:
        prev_net = net
        time.sleep(FREQUENCY)
        continue
    
    upload_kbps = ((net.bytes_sent - prev_net.bytes_sent)) / (1024 * FREQUENCY)
    download_kbps = ((net.bytes_recv - prev_net.bytes_recv)) / (1024 * FREQUENCY)

    new_stat = Stat(
        timestamp=timestamp,
        cpu=round(cpu, 2),
        upload_kbps=round(upload_kbps, 2),
        download_kbps=round(download_kbps, 2),
        mem_gb=round(mem_gb, 3)
    )
    
    session.add(new_stat)
    
    if loop_count % 60 == 0:
        threshold = timestamp - MAX_AGE_SECONDS
        session.query(Stat).filter(Stat.timestamp < threshold).delete()
    
    session.commit()
    print(f"{timestamp}\t{cpu:.2f}\t{upload_kbps:.2f}\t{download_kbps:.2f}\t{mem_gb:.3f}")
    
    prev_net = net
    loop_count += 1
    time.sleep(FREQUENCY)
