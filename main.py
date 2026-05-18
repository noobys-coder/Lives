import requests
import os
import json
import time

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHANNEL_ID')

DATA_FILE = 'auctions_state.json'

def load_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_state(state):
    with open(DATA_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def delete_message(message_id):
    url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
    payload = {"chat_id": CHAT_ID, "message_id": message_id}
    requests.post(url, json=payload)

def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload)
    return r.json()

# Dummy Scraper zum Testen
def check_fragment():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        requests.get("https://fragment.com/", headers=headers, timeout=15)
        return [
            {"type": "bid", "username": "@gamerpro", "amount": 67},
            {"type": "bid", "username": "@saturnx", "amount": 135},
            {"type": "mint", "username": "@freshnewone", "amount": 0}
        ]
    except:
        return []

# Hauptlogik
state = load_state()
new_events = check_fragment()

for event in new_events:
    username = event["username"]
    amount = event["amount"]
    current = state.get(username, {"message_id": None, "amount": 0})
    
    if amount > current["amount"] or current["message_id"] is None:
        if current.get("message_id"):
            delete_message(current["message_id"])
        
        if event["type"] == "bid":
            text = f"""🔨 <b>New bid on username!</b>

Amount: <b>{amount} TON</b>
Username: {username}

More services"""
        else:
            text = f"""✨ <b>New username minted!</b>

Username: {username}
No bids yet

More services"""
        
        response = send_message(text)
        
        if response.get("ok"):
            state[username] = {
                "message_id": response["result"]["message_id"],
                "amount": amount
            }
            save_state(state)
            print(f"✅ {username} → {amount} TON")
        else:
            print(f"Fehler bei {username}")

print("✅ Durchlauf beendet")
