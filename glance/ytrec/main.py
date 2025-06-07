from flask import Flask, request
import pandas as pd
import threading
import time
import os
from flask import jsonify
from llm import is_song, clean_title

app = Flask(__name__)

TMP_FILE = 'his.tmp'
CSV_FILE = 'history.csv'
PROCESSING_FILE = "his.processing.tmp"

@app.route('/update_history', methods=['POST'])
def receive_history():
    data = request.get_json()
    print(f"Received: {data}")

    vid = data.get('url').split('v=')[-1].split('&')[0]  # Extract video ID from URL
    data["thumbnail"] = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
    
    df = pd.DataFrame([data])
    df.to_csv(TMP_FILE, mode='a', index=False, header=not os.path.exists(TMP_FILE))
    return '', 204
    
@app.route('/get_videos', methods=['GET'])
def get_videos():
    try:
        df = pd.read_csv('history.csv')
        sample = df.sample(n=min(5, len(df)))
        return jsonify(sample.to_dict(orient='records'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def should_store_and_clean(title):
    if not is_song(title):
        return False, None
    cleaned_title = clean_title(title)
    time.sleep(2)  # Bro! Give the pi some time to breathe
    return True, cleaned_title

def hourly_processor():
    while True:
        time.sleep(30 * 60)

        if not os.path.exists(TMP_FILE):
            continue

        try:
            df = pd.read_csv(TMP_FILE)
            os.replace(TMP_FILE, PROCESSING_FILE)
        except Exception as e:
            print(f"Could not read or rename tmp file: {e}")
            continue

        df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce').fillna(0)
        df = df.drop_duplicates(subset='url', keep='last')

        filtered_rows = []
        try:
            print("Getting llm results")
            for i, row in df.iterrows():
                print(f"{i+1}/{len(df)}: {row['title']}")
                keep, cleaned_title = should_store_and_clean(row['title'])
                if keep:
                    row['title'] = cleaned_title
                    filtered_rows.append(row)
        except Exception as e:
            print(f"Error processing LLM batch: {e}")
            continue

        if filtered_rows:
            final_df = pd.DataFrame(filtered_rows)
            final_df = final_df.sort_values('timestamp', ascending=False)
            final_df.to_csv(CSV_FILE, index=False)

        try:
            os.remove(PROCESSING_FILE)
        except Exception as e:
            print(f"Error deleting processing file: {e}")  # which is fine... 


# Start background processor
threading.Thread(target=hourly_processor, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5500, debug=False)




