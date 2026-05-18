import requests
import os
import json
import time
from datetime import datetime
from ton_fragment.usernames.usernames import Usernames

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHANNEL_ID')

DATA_FILE = 'auctions_state.json'

# === Konfiguration ===
CHECK_INTERVAL = 30  # Alle 30 Sekunden prüfen (anpassen nach Bedarf)
MAX_USERNAMES = 15   # Top 15 Auktionen

def load_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Fehler beim Laden der State: {e}")
            pass
    return {}

def save_state(state):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern der State: {e}")

def delete_message(message_id):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
        payload = {"chat_id": CHAT_ID, "message_id": message_id}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"⚠️ Fehler beim Löschen der Nachricht: {e}")

def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=5)
        return r.json()
    except Exception as e:
        print(f"⚠️ Fehler beim Senden der Nachricht: {e}")
        return {"ok": False}

# === Echter Scraper mit ton-fragment ===
def check_fragment():
    try:
        # Hole aktuelle Auctions (höchste Gebote)
        auctions = Usernames('auction')   # 'auction' = laufende Gebote
        events = []
        
        for item in auctions.result[:MAX_USERNAMES]:  # Top N prüfen
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
        
        return events
        
    except Exception as e:
        print(f"❌ Scraper Fehler: {e}")
        return []

def log_timestamp():
    """Gib den aktuellen Zeitstempel aus"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def process_events(state, new_events):
    """Verarbeite alle Events und aktualisiere State"""
    processed = 0
    
    for event in new_events:
        username = event["username"]
        amount = event["amount"]
        current = state.get(username, {"message_id": None, "amount": 0})
        
        # Nur senden wenn: Menge höher ODER erste Nachricht
        if amount > current["amount"] or current["message_id"] is None:
            
            # Alten Post löschen
            if current.get("message_id"):
                delete_message(current["message_id"])
                time.sleep(0.5)  # Kleine Pause zwischen API-Calls
            
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
                print(f"✅ [{log_timestamp()}] {username} → {amount} TON")
                processed += 1
            else:
                print(f"❌ [{log_timestamp()}] Telegram Fehler bei {username}")
                print(f"   Response: {response}")
    
    return state, processed

# === HAUPTPROGRAMM - ENDLOSSCHLEIFE ===
print(f"🚀 [{log_timestamp()}] Starte Auktions-Monitor...")
print(f"⏱️  Prüf-Intervall: {CHECK_INTERVAL} Sekunden")
print(f"📊 Überwache Top {MAX_USERNAMES} Auktionen\n")

iteration = 0

try:
    while True:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"📡 Durchlauf #{iteration} - [{log_timestamp()}]")
        print(f"{'='*60}")
        
        # Lade State
        state = load_state()
        
        # Prüfe auf neue Events
        new_events = check_fragment()
        
        if new_events:
            print(f"🔍 {len(new_events)} Auktionen gefunden")
            state, processed = process_events(state, new_events)
            print(f"📢 {processed} Benachrichtigungen gesendet")
        else:
            print(f"⚠️  Keine Events gefunden oder Scraper-Fehler")
        
        # Warte bis nächster Check
        print(f"\n⏰ Nächste Prüfung in {CHECK_INTERVAL} Sekunden...")
        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print(f"\n\n🛑 [{log_timestamp()}] Monitor beendet durch Benutzer")
except Exception as e:
    print(f"\n\n❌ [{log_timestamp()}] Kritischer Fehler: {e}")
    print("⚠️  Programm beendet")
