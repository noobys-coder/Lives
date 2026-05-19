import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib

# Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise ValueError("TELEGRAM_TOKEN und CHAT_ID müssen als Environment-Variablen gesetzt sein!")

JSON_FILE = "sent_bids.json"

def load_sent_bids():
    """Lädt bereits gesendete Gebote aus JSON."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Als Set von Hashes für schnelle Lookup
                return set(data)
        except:
            return set()
    return set()

def save_sent_bids(sent_bids):
    """Speichert gesendete Gebote."""
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_bids), f, ensure_ascii=False, indent=2)

def generate_bid_hash(username, amount, timestamp):
    """Erzeugt einen eindeutigen Hash für ein Gebot (verhindert Duplikate)."""
    key = f"{username}|{amount}|{timestamp}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()

def send_telegram(message):
    """Sendet Nachricht via Telegram Bot."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"Telegram Fehler: {response.text}")
    except Exception as e:
        print(f"Telegram Sende-Fehler: {e}")

def get_recent_bids():
    """
    Scrapt die NEUESTEN Gebote von fragment.com.
    **Passe die Selector an die aktuelle HTML-Struktur an!**
    """
    url = "https://fragment.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        bids = []
        
        # === WICHTIG: Hier Selector für "Recent Activity" / Latest Bids anpassen ===
        # Beispiel-Platzhalter (passe an echte Struktur an):
        activity_items = soup.select("div.recent-activity div.bid-item, tr.bid-row, .activity-log div")  # <-- ANPASSEN!
        
        for item in activity_items[:20]:  # Begrenzen
            try:
                # Beispiele für mögliche Selector (anpassen!):
                username_tag = item.select_one("a.username, .user, span.name")
                amount_tag = item.select_one(".bid-amount, .price, .ton-amount")
                time_tag = item.select_one(".timestamp, .time, time")
                
                if not username_tag or not amount_tag:
                    continue
                    
                username = username_tag.get_text(strip=True).replace("@", "").strip()
                amount = amount_tag.get_text(strip=True)
                timestamp = time_tag.get_text(strip=True) if time_tag else datetime.now().strftime("%Y-%m-%d %H:%M")
                
                if username and amount:
                    bids.append({
                        "username": username,
                        "amount": amount,
                        "timestamp": timestamp
                    })
            except:
                continue
                
        return bids
        
    except Exception as e:
        print(f"Scraping Fehler: {e}")
        return []

def filter_valid_usernames(bids):
    """Filtert Usernames mit 5-10 Zeichen."""
    valid = []
    for bid in bids:
        if 5 <= len(bid["username"]) <= 10:
            valid.append(bid)
    return valid

def main_loop():
    print("🚀 Fragment Recent Bids Monitor gestartet...")
    sent_bids = load_sent_bids()
    
    while True:
        try:
            recent_bids = get_recent_bids()
            valid_bids = filter_valid_usernames(recent_bids)
            
            new_count = 0
            for bid in valid_bids:
                bid_hash = generate_bid_hash(
                    bid["username"], 
                    bid["amount"], 
                    bid["timestamp"]
                )
                
                if bid_hash not in sent_bids:
                    message = f"""
🔔 <b>Neues Gebot auf Fragment</b>

👤 <b>Username:</b> @{bid['username']}
💰 <b>Betrag:</b> {bid['amount']}
⏰ <b>Zeit:</b> {bid['timestamp']}
                    """.strip()
                    
                    send_telegram(message)
                    sent_bids.add(bid_hash)
                    new_count += 1
                    
            if new_count > 0:
                save_sent_bids(sent_bids)
                print(f"✅ {new_count} neue Gebote gesendet.")
            
        except Exception as e:
            print(f"Fehler in Loop: {e}")
        
        time.sleep(5)  # Alle 5 Sekunden

if __name__ == "__main__":
    main_loop()
