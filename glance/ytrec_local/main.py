#!/usr/bin/env python3

import sqlite3, os, time, requests

print("started")

HIST = os.path.expanduser('/brave/History')
TEMP = 'brave_history_temp.sqlite'
API = 'http://192.168.29.2:5500/update_history'
STAMP = 'last_timestamp.txt'
INTERVAL = 15  # seconds

def get_ts(): return int(open(STAMP).read()) if os.path.exists(STAMP) else 0
def set_ts(ts): open(STAMP, 'w').write(str(ts))

def fetch_new(since):
    with open(HIST, 'rb') as f, open(TEMP, 'wb') as t: t.write(f.read())
    q = """
        SELECT url, title, last_visit_time FROM urls
        WHERE last_visit_time > ?
        ORDER BY last_visit_time ASC
    """
    with sqlite3.connect(f'file:{TEMP}?mode=ro', uri=True) as conn:
        return conn.execute(q, (since,)).fetchall()

queue = []
while True:
    print("Checking for new history entries...")
    try:
        hist = fetch_new(get_ts())
    except Exception as e:
        print("Error fetching history")
        print(e)
        time.sleep(INTERVAL)
        continue
    
    for url, title, timestamp in hist:
        if 'www.youtube.com/watch' in url and 'shorts' not in url:
            url = url.split('&')[0]
            print(f"New video detected: {title} ({url})")
            queue.append((url, title, timestamp))

    try:
        while len(queue) > 0:
            url, title, timestamp = queue[0]
            requests.post(API, json={'timestamp': timestamp, 'title': title, 'url': url})
            print(f"Successfully sent: {title} ({url})")
            queue.pop(0)
            set_ts(timestamp)
            time.sleep(0.1)  # Avoid overwhelming the server
    except Exception as e:
        print("Error: Could not send data")
        print(e)
    time.sleep(INTERVAL)
