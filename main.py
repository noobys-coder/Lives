import requests
import os
import json
import time
from ton_fragment.usernames.usernames import Usernames

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

# === Echter Scraper mit ton-fragment ===
def check_fragment():
    try:
        # Hole aktuelle Auctions (höchste Gebote)
        auctions = Usernames('auction')   # 'auction' = laufende Gebote
        events = []
        
        for item in auctions.result[:15]:  # Top 15 prüfen
            if not item or 'username' not in item:
                continue
                
            username = f"@{item.get('username', '')}"
            try:
                amount = int(item.get('price', 0)) if item.get('price') else 0
            except:
                amount = 0
                
            events.append({
                "type": "bid",
                "username": username,
                "amount": amount
            })
        
        # Hier könntest du später auch neue Mintings hinzufügen
        return events
        
    except Exception as e:
        print("Scraper Fehler:", e)
        # Fallback Dummy falls Library nicht funktioniert
        return [
            {"type": "bid", "username": "@testuser", "amount": 50}
        ]

# Hauptlogik
state = load_state()
new_events = check_fragment()

for event in new_events:
    username = event["username"]
    amount = event["amount"]
    current = state.get(username, {"message_id": None, "amount": 0})
    
    if amount > current["amount"] or current["message_id"] is None:
        
        # Alten Post löschen
        if current.get("message_id"):
            delete_message(current["message_id"])
        
        # Neuen Post senden
        if event["type"] == "bid":
            text = f"""🔨 <b>New bid on username!</b>

Amount: <b>{amount} TON</b>
Username: {username}"""
        else:
            text = f"""✨ <b>New username minted!</b>

Username: {username}
No bids yet"""
        
        response = send_message(text)
        
        if response.get("ok"):
            state[username] = {
                "message_id": response["result"]["message_id"],
                "amount": amount
            }
            save_state(state)
            print(f"✅ {username} → {amount} TON")
        else:
            print(f"Telegram Fehler bei {username}")

print("✅ Durchlauf beendet")
