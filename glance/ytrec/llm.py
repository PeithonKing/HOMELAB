import ollama
import requests
from bs4 import BeautifulSoup

# Specify the model to use
# model_name = 'qwen3:4b'
# model_name = 'gemma2:2b'
# model_name = 'gemma3:1b'
model_name = 'gemma3'

client = ollama.Client(host='http://192.168.29.2:11434')

def is_song(title):
    system_prompt = """You are a classifier. You determine whether a YouTube video title refers to a song. Respond with one of the following:
- "SONG" if the title clearly indicates a song.
- "VIDEO" if the title clearly does not indicate a song.
- "UNCLEAR" if it's unclear.
Respond with only the classification label, without any additional text. Pick one of the options above.
"""
    response = client.generate(model=model_name, prompt=title, system=system_prompt, think=False, keep_alive=30)
    classification = response.response.strip().upper()
    print(f"Classification: {classification}")
    return classification == "SONG"

def clean_title_llm(title, url):
    system_prompt = """You are a title cleaner. Clean up YouTube song titles for storage. Your goal is to keep only:
- The name of the song
- The artist (only if present in the title)
- Optional: language, studio etc (only if present in the title)
Remove anything else: video platform mentions, episode numbers, timestamps, redundant brackets, quotes, tags, emojis, etc.

Examples:
- "Are Robot Vacuums FINALLY Worth Buying in 2025? - YouTube" -> "Are Robot Vacuums FINALLY Worth Buying in 2025?"
- "(10) Best Robot Vacuum Cleaner 2025 - YouTube" -> "Best Robot Vacuum Cleaner 2025"
- "(11) Sei To Abar Kachhe Ele - YouTube" -> "Sei To Abar Kachhe Ele"
- "झाड़ू पोछा का रोबोट की वजह से मेरी ज़िंदगी पहली सी नहीं रही Vaccum Mop Robot Review 😳 - YouTube" -> "Mop Robot Review"

Respond only with the cleaned version. No extra text. Do not add any text which is not part of the song name or artist. Do not put in quotes.
"""
    response = client.generate(model=model_name, prompt=title, system=system_prompt, think=False, keep_alive=30)
    new_title = response.response.strip()
    print(f"Cleaned title: {new_title}")
    return new_title

def clean_title(title, url):
    # User-Agent string for Firefox on Linux
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('title')

        if title_tag:
            full_title = title_tag.get_text()
            # YouTube titles usually end with " - YouTube", so we remove it
            if full_title.endswith(" - YouTube"):
                return full_title[:-len(" - YouTube")]
            return full_title
        else:
            print("Title tag not found in the page.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

