import requests
import os
import json
import time
from datetime import datetime

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHANNEL_ID')

DATA_FILE = 'seen_auctions.json'

# === Konfiguration ===
CHECK_INTERVAL = 5          # Sekunden zwischen Checks
MIN_USERNAME_LENGTH = 5     # Mindestens 5 Zeichen
MAX_USERNAME_LENGTH = 10    # Maximal 10 Zeichen

def load_seen_auctions():
    """Lade bereits gemeldete Auktionen"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                return data.get('seen', {})
        except Exception as e:
            print(f"⚠️ Fehler beim Laden: {e}")
    return {}

def save_seen_auctions(seen):
    """Speichere gemeldete Auktionen"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump({'seen': seen}, f)
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern: {e}")

def send_message(text):
    """Sende Nachricht zu Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=5)
        return r.json()
    except Exception as e:
        print(f"⚠️ Fehler beim Senden: {e}")
        return {"ok": False}

def is_valid_username_length(username):
    """Prüfe Username-Länge"""
    if not username:
        return False
    clean_name = username.lstrip('@').lower()
    length = len(clean_name)
    return MIN_USERNAME_LENGTH <= length <= MAX_USERNAME_LENGTH

def get_auctions_tonapi():
    """Hole aktive Auktionen von TonAPI (Alternative zu Fragment)"""
    try:
        url = "https://tonapi.io/v2/nft/collections/EQB3ncyBUTjZUA5iQF47VJibaSMSqcsbLW2alyMXxZ-PE6bO/items"
        
        headers = {
            'accept': 'application/json',
        }
        
        params = {
            'limit': 200,
            'offset': 0,
            'sort': 'recently_updated'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            events = []
            for item in items:
                try:
                    # Extrahiere Username aus metadata
                    metadata = item.get('metadata', {})
                    name = metadata.get('name', '')
                    
                    if not name:
                        continue
                    
                    # Bereinige Namen
                    username = '@' + name.lower().replace('@', '').strip()
                    
                    # Prüfe Länge
                    if not is_valid_username_length(username):
                        continue
                    
                    # Hole Price info
                    sale = item.get('sale', {})
                    price_str = "Unknown"
                    
                    if sale:
                        price = sale.get('price', {})
                        if isinstance(price, dict):
                            value = price.get('value', '0')
                        else:
                            value = str(price)
                        
                        try:
                            # Konvertiere zu TON
                            value_int = int(value)
                            price_ton = value_int / (10 ** 9)
                            price_str = f"{price_ton:.2f}"
                        except:
                            price_str = value
                    
                    # Unique ID für Duplikat-Check
                    unique_id = f"{username}_{price_str}"
                    
                    events.append({
                        'id': unique_id,
                        'username': username,
                        'amount': price_str,
                    })
                except Exception as e:
                    continue
            
            return events
        else:
            print(f"⚠️ TonAPI Response: {response.status_code}")
            return []
        
    except Exception as e:
        print(f"❌ TonAPI Fehler: {e}")
        return []

def get_auctions_ton_fragment_direct():
    """Hole direkt von ton-fragment.io die Auktionen"""
    try:
        # Direkt JSON von Fragment API
        url = "https://fragment.com/api/v2/auctions"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            events = []
            
            # Verarbeite Auktionen
            auctions = data.get('auctions', [])
            for auction in auctions:
                try:
                    username = auction.get('username', '')
                    if not username:
                        continue
                    
                    username = '@' + username.lower().strip()
                    
                    if not is_valid_username_length(username):
                        continue
                    
                    # Hole aktuelles Gebot
                    price_data = auction.get('bidAmount', {})
                    
                    if isinstance(price_data, dict):
                        price_str = price_data.get('pretty', 'Unknown')
                    else:
                        price_str = str(price_data)
                    
                    unique_id = f"{username}_{price_str}"
                    
                    events.append({
                        'id': unique_id,
                        'username': username,
                        'amount': price_str,
                    })
                except Exception as e:
                    continue
            
            return events
        else:
            print(f"⚠️ Fragment Response: {response.status_code}")
            return []
        
    except Exception as e:
        print(f"❌ Fragment API Fehler: {e}")
        return []

def log_timestamp():
    """Aktueller Zeitstempel"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def process_events(seen, events):
    """Verarbeite neue Events"""
    new_seen = dict(seen)
    processed = 0
    
    for event in events:
        event_id = event['id']
        
        # Prüfe ob Event schon gemeldet wurde
        if event_id in seen:
            continue
        
        new_seen[event_id] = True
        username = event['username']
        amount = event['amount']
        
        # Sende Benachrichtigung
        text = f"""🔨 <b>New bid on username!</b>

Amount: <b>{amount} TON</b>
Username: {username}"""
        
        response = send_message(text)
        
        if response.get('ok'):
            print(f"✅ [{log_timestamp()}] {username} → {amount} TON")
            processed += 1
        else:
            print(f"❌ [{log_timestamp()}] Telegram Fehler bei {username}")
            print(f"   Response: {response}")
    
    return new_seen, processed

# === HAUPTPROGRAMM ===
print(f"🚀 [{log_timestamp()}] Starte Fragment.com Live Monitor...")
print(f"⏱️  Prüf-Intervall: {CHECK_INTERVAL} Sekunden")
print(f"📊 Überwache Usernames mit {MIN_USERNAME_LENGTH}-{MAX_USERNAME_LENGTH} Zeichen")
print(f"📢 Zeige ALLE neuen Gebote & Mints\n")

iteration = 0
seen_auctions = load_seen_auctions()

try:
    while True:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"📡 Durchlauf #{iteration} - [{log_timestamp()}]")
        print(f"{'='*60}")
        
        # Versuche Fragment API
        events = get_auctions_ton_fragment_direct()
        
        if not events:
            print(f"⚠️  Fragment API nicht verfügbar, versuche TonAPI...")
            events = get_auctions_tonapi()
        
        if events:
            print(f"🔍 {len(events)} Auktionen gefunden")
            seen_auctions, processed = process_events(seen_auctions, events)
            save_seen_auctions(seen_auctions)
            print(f"📢 {processed} NEUE Benachrichtigungen gesendet")
            print(f"📊 Insgesamt {len(seen_auctions)} verschiedene Auktionen gemeldet")
        else:
            print(f"⚠️  Keine Auktionen gefunden")
        
        # Warte
        print(f"\n⏰ Nächste Prüfung in {CHECK_INTERVAL} Sekunden...")
        time.sleep(CHECK_INTERVAL)

except KeyboardInterrupt:
    print(f"\n\n🛑 [{log_timestamp()}] Monitor beendet durch Benutzer")
except Exception as e:
    print(f"\n\n❌ [{log_timestamp()}] Kritischer Fehler: {e}")
    import traceback
    traceback.print_exc()
    print("⚠️  Programm beendet")
