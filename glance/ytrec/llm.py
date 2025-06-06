import ollama

# Specify the model to use
# model_name = 'qwen3:4b'
# model_name = 'gemma2:2b'
# model_name = 'gemma3:1b'
model_name = 'gemma3'

client = ollama.Client(host='http://localhost:11434')


def is_song(title):
    system_prompt = """
You are a classifier. You determine whether a YouTube video title refers to a song. Respond with one of the following:
- "SONG" if the title clearly indicates a song.
- "VIDEO" if the title clearly does not indicate a song.
- "UNCLEAR" if it's unclear.
Respond with only the classification label, without any additional text. Pick one of the options above.
"""
    response = client.generate(model=model_name, prompt=title, system=system_prompt, think=False)
    classification = response.response.strip().upper()
    return classification == "SONG"

def clean_title(title):
    system_prompt = """
You are a title cleaner. Clean up YouTube song titles for storage. Your goal is to keep only:
- The name of the song (if available)
- The main artist
- Optional: language, studio etc
Remove anything else: video platform mentions, episode numbers, timestamps, redundant brackets, quotes, tags, emojis, etc. Output format:

Song Name (if available) | Artist Name (if available) | Optional info 

Respond only with the cleaned version. No extra text.
"""
    response = client.generate(model=model_name, prompt=title, system=system_prompt, think=False)
    return response.response.strip()
