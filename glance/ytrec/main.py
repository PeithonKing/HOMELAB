from flask import Flask, request, Response, jsonify
import pandas as pd
import threading, time, os, json, random
import xml.etree.ElementTree as ET

from llm import is_song, clean_title
from bs4 import BeautifulSoup
from datetime import datetime
import requests


app = Flask(__name__)

TMP_FILE = 'his.tmp'
PROCESSING_FILE = "his.processing.tmp"
HISTORY_FILE = 'history.json'

@app.route('/update_history', methods=['POST'])
def receive_history():
    data = request.get_json()
    print(f"Received: {data}")

    vid_key = data.get('url').split('v=')[-1].split('&')[0]
    data["vid_key"] = vid_key

    df = pd.DataFrame([data])
    df.to_csv(TMP_FILE, mode='a', index=False, header=not os.path.exists(TMP_FILE))
    return '', 204
    
@app.route('/get_videos', methods=['GET'])
def get_videos():
    try:
        with open(HISTORY_FILE, 'r') as f:
            data = json.load(f)
        videos = list(data.values())
        sample = random.sample(videos, k=min(10, len(videos)))
        result = [
            {
                "title": video["title"],
                "url": video["url"],
                "thumbnail": video["thumbnail"]
            }
            for video in sample
        ]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def should_store_and_clean(title, url):
    if not is_song(title):
        return False, None
    cleaned_title = clean_title(title, url)
    time.sleep(3)  # Bro! Give the pi some time to breathe
    return True, cleaned_title

def hourly_processor():
    while True:
        
        save_rss_to_file()
        
        # print started and time
        print(f"Starting processing at {time.ctime()}")
        time.sleep(60*60)

        if not os.path.exists(TMP_FILE) and not os.path.exists(PROCESSING_FILE):
            print("No new data to process.")
            continue
        
        print("Processing new data...")
        try:
            tmp_df = pd.read_csv(TMP_FILE) if os.path.exists(TMP_FILE) else pd.DataFrame()
            proc_df = pd.read_csv(PROCESSING_FILE) if os.path.exists(PROCESSING_FILE) else pd.DataFrame()
            df = pd.concat([tmp_df, proc_df], ignore_index=True)
            df.to_csv(PROCESSING_FILE, index=False)
            if os.path.exists(TMP_FILE): os.remove(TMP_FILE)
            print("Read and renamed tmp file successfully.")
        except Exception as e:
            print(f"Could not read or rename tmp file: {e}")
            continue
        
        # Load existing JSON history
        print("Loading existing history...")
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                old_database = json.load(f)
        else:
            old_database = {}
        print(f"Loaded {len(old_database)} existing entries.")

        try:
            print("Processing entries...")
            for i, row in df.iterrows():
                timestamp = int(row['timestamp'])
                title = row['title']
                url = row['url']
                vid_key = row['vid_key']

                if len(vid_key)!=11: continue

                if vid_key in old_database:
                    if timestamp not in old_database[vid_key]["watches"]:
                        old_database[vid_key]["watches"].append(timestamp)
                else:
                    keep, cleaned_title = should_store_and_clean(title, url)
                    if not keep: continue
                    old_database[vid_key] = {
                        "title": cleaned_title,
                        "url": url,
                        "thumbnail": f"https://img.youtube.com/vi/{vid_key}/hqdefault.jpg",
                        "watches": [timestamp,]
                    }
        except Exception as e:
            print(f"Error processing entries: {e}")
            continue

        # Save updated database to HISTORY_FILE
        try:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(old_database, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Could not save updated history: {e}")
            continue

        # Cleanup
        try:
            os.remove(PROCESSING_FILE)
        except Exception as e:
            print(f"Error deleting processing file: {e}")


def generate_rss_feed():
    # Fetch the blog page
    url = "https://ollama.com/blog"
    response = requests.get(url)
    response.raise_for_status()
    # Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    # Create RSS feed structure
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    # Add channel metadata
    ET.SubElement(channel, 'title').text = "Ollama Blog"
    ET.SubElement(channel, 'link').text = url
    ET.SubElement(channel, 'description').text = "Latest posts from Ollama blog"
    ET.SubElement(channel, 'lastBuildDate').text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    # Find all blog posts
    posts = soup.select('section.mx-auto a.group')
    for post in posts:
        # Extract post details
        title = post.select_one('h2').text.strip()
        link = "https://ollama.com" + post['href']
        pub_date = post.select_one('h3').text.strip()
        description = post.select_one('p').text.strip()
        # Create RSS item
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = title
        ET.SubElement(item, 'link').text = link
        ET.SubElement(item, 'description').text = description
        ET.SubElement(item, 'pubDate').text = pub_date
        ET.SubElement(item, 'guid').text = link
        ET.SubElement(item, 'enclosure', url="https://images.seeklogo.com/logo-png/59/1/ollama-logo-png_seeklogo-593420.png", type='image/png', length='100')
    # Convert to XML string
    xml_str = ET.tostring(rss, encoding='utf-8', method='xml').decode()
    return xml_str

def save_rss_to_file():
    try: new_content = generate_rss_feed()
    except: return
    file_path = "static/rss/ollama_rss.xml"
    
    try:
        with open(file_path, "r") as f:
            current_content = f.read()
    except FileNotFoundError:
        current_content = ""

    if current_content != new_content:
        with open(file_path, "w") as f:
            f.write(new_content)



# Start background processor
threading.Thread(target=hourly_processor, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5500, debug=False)
