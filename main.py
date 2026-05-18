import requests
import os
import json
import time
from datetime import datetime

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHANNEL_ID')

DATA_FILE = 'seen_txs.json'  # Speichere TX-Hashes statt Namen (verhindert Duplikate)

# === Konfiguration ===
CHECK_INTERVAL = 5          # Schneller checken (5 Sekunden)
MIN_USERNAME_LENGTH = 5     # Mindestens 5 Zeichen
MAX_USERNAME_LENGTH = 10    # Maximal 10 Zeichen

# TON Blockchain API
TON_RPC = "https://toncenter.com/api/v2"
GETGEMS_ADDRESS = "EQB3ncyBUTjZUA5iQF47VJibaSMSqcsbLW2alyMXxZ-PE6bO"  # GetGems NFT Collection

def load_seen_txs():
    """Lade bereits gesehene Transaktions-Hashes"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get('seen_txs', []))
        except Exception as e:
            print(f"⚠️ Fehler beim Laden: {e}")
    return set()

def save_seen_txs(seen_txs):
    """Speichere gesehene Transaktions-Hashes"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump({'seen_txs': list(seen_txs)}, f)
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

def extract_username_from_tx(tx_data):
    """Extrahiere Username aus Transaction Data"""
    try:
        # Versuche den Username aus verschiedenen Feldern zu extrahieren
        if 'in_msg' in tx_data and tx_data['in_msg']:
            msg = tx_data['in_msg']
            
            # Versuche aus dem Message-Text zu extrahieren
            if 'message' in msg:
                message = msg['message']
                # Suche nach Mustern wie "@username"
                if '@' in message:
                    parts = message.split('@')
                    for part in parts[1:]:
                        # Nehme die ersten Zeichen bis zu einem Trennzeichen
                        username = ''.join(c for c in part.split()[0] if c.isalnum() or c in '-_')
                        if username and is_valid_username_length(username):
                            return '@' + username
        
        # Alternative: Versuche aus Operation zu erkennen
        if 'op_type' in tx_data:
            op = tx_data['op_type']
            if 'bid' in op.lower() or 'auction' in op.lower():
                # Extrahiere aus Body oder anderen Feldern
                return None
                
    except Exception as e:
        pass
    
    return None

def get_transactions():
    """Hole neueste Transaktionen von TON Blockchain"""
    try:
        # Hole Transaktionen vom GetGems Contract
        url = f"{TON_RPC}/getTransactions"
        params = {
            "account": GETGEMS_ADDRESS,
            "limit": 100,  # Hole mehr Transaktionen
            "archival": False
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            return data.get('result', [])
    except Exception as e:
        print(f"❌ Fehler beim Abrufen von Transaktionen: {e}")
    
    return []

def get_nft_transfers():
    """Alternative: Hole NFT Transfers direkt"""
    try:
        # Nutze TON API für NFT Transfers
        # Dies ist eine direkte Abfrage auf neue NFT-Transfers
        url = f"{TON_RPC}/getTransactions"
        
        # Suche nach Transactions die NFT-Transfers sind
        params = {
            "account": GETGEMS_ADDRESS,
            "limit": 50,
            "archival": False
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        events = []
        
        if data.get('ok'):
            for tx in data.get('result', []):
                tx_hash = tx.get('transaction_id', {}).get('hash', '')
                
                # Versuche Username zu extrahieren
                username = None
                
                # Methode 1: Aus Comment
                if 'in_msg' in tx and tx['in_msg']:
                    if 'message' in tx['in_msg']:
                        msg_text = tx['in_msg']['message']
                        # Suche nach Usernamen im Format: "username" oder "@username"
                        import re
                        matches = re.findall(r'@?([a-z0-9_-]{5,10})', msg_text.lower())
                        if matches:
                            username = '@' + matches[0]
                
                # Methode 2: Aus der Transaktion selbst
                if not username and 'out_msgs' in tx:
                    for msg in tx.get('out_msgs', []):
                        if 'message' in msg:
                            import re
                            matches = re.findall(r'@?([a-z0-9_-]{5,10})', msg['message'].lower())
                            if matches:
                                username = '@' + matches[0]
                                break
                
                # Prüfe Länge
                if username and is_valid_username_length(username):
                    # Bestimme ob es ein neues Gebot oder ein Mint ist
                    tx_type = "bid"
                    amount_str = "Unknown"
                    
                    # Versuche Betrag zu extrahieren
                    if 'out_msgs' in tx and tx['out_msgs']:
                        for msg in tx['out_msgs']:
                            if 'value' in msg:
                                try:
                                    # Konvertiere zu TON (1 TON = 10^9 nanoton)
                                    amount_nanoton = int(msg['value'])
                                    amount_ton = amount_nanoton / (10 ** 9)
                                    amount_str = f"{amount_ton:.2f}"
                                except:
                                    pass
                    
                    events.append({
                        'tx_hash': tx_hash,
                        'username': username,
                        'amount': amount_str,
                        'type': tx_type,
                        'timestamp': tx.get('utime', int(time.time()))
                    })
        
        return events
        
    except Exception as e:
        print(f"❌ Fehler bei NFT Transfers: {e}")
    
    return []

def log_timestamp():
    """Aktueller Zeitstempel"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def process_events(seen_txs, events):
    """Verarbeite neue Events"""
    new_seen = set(seen_txs)
    processed = 0
    
    for event in events:
        tx_hash = event['tx_hash']
        
        # Prüfe ob TX schon gesehen wurde
        if tx_hash in seen_txs:
            continue
        
        new_seen.add(tx_hash)
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
    
    return new_seen, processed

# === HAUPTPROGRAMM ===
print(f"🚀 [{log_timestamp()}] Starte Blockchain Live Monitor...")
print(f"⏱️  Prüf-Intervall: {CHECK_INTERVAL} Sekunden")
print(f"🔗 Verbunden mit: {TON_RPC}")
print(f"📊 Überwache Usernames mit {MIN_USERNAME_LENGTH}-{MAX_USERNAME_LENGTH} Zeichen")
print(f"📢 Zeige ALLE neuen Gebote & Mints auf der Blockchain\n")

iteration = 0
seen_txs = load_seen_txs()

try:
    while True:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"📡 Durchlauf #{iteration} - [{log_timestamp()}]")
        print(f"{'='*60}")
        
        # Hole NFT Transfers von Blockchain
        events = get_nft_transfers()
        
        if events:
            print(f"🔍 {len(events)} Transaktionen gefunden")
            seen_txs, processed = process_events(seen_txs, events)
            save_seen_txs(seen_txs)
            print(f"📢 {processed} NEUE Benachrichtigungen gesendet")
            print(f"📊 Insgesamt {len(seen_txs)} verschiedene Transaktionen gespeichert")
        else:
            print(f"⚠️  Keine neuen Transaktionen gefunden")
        
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
