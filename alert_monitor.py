import time
import requests
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def send_alert(message: str) -> None:
    print(f"[ALERT] {message}")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🚨 <b>OPERATIONAL ALERT</b>\n\n{message}", "parse_mode": "HTML"},
            timeout=5
        )
    except Exception as e:
        print(f"Failed to send telegram alert: {e}")

def main():
    last_alerted = set()
    print("Starting operational alert monitor...")
    
    while True:
        current_alerts = set()
        try:
            resp = requests.get("http://localhost:8000/health", timeout=5)
            if resp.status_code != 200:
                current_alerts.add("Backend returned non-200 status code.")
            else:
                data = resp.json()
                crits = data.get("critical_states", {})
                if crits.get("bybit_disconnected"):
                    current_alerts.add("Bybit API disconnected or auth failure.")
                if crits.get("scanner_stalled"):
                    current_alerts.add("Scanner is stalled/stale.")
                if crits.get("db_write_failure"):
                    current_alerts.add("Database is unavailable or write failed.")
                if crits.get("stale_reconciliation"):
                    current_alerts.add("Reconciliation mismatch or stale.")
                if crits.get("manager_inactive"):
                    current_alerts.add("Position manager inactive with open positions (BE failure risk).")
        except requests.exceptions.RequestException:
            current_alerts.add("Backend is down / unreachable.")

        # Send new alerts
        new_alerts = current_alerts - last_alerted
        for alert in new_alerts:
            send_alert(alert)
        
        # We also want to notify when an alert resolves
        resolved_alerts = last_alerted - current_alerts
        for alert in resolved_alerts:
            print(f"[RESOLVED] {alert}")
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={"chat_id": TELEGRAM_CHAT_ID, "text": f"✅ <b>ALERT RESOLVED</b>\n\n{alert}", "parse_mode": "HTML"},
                        timeout=5
                    )
                except Exception:
                    pass

        last_alerted = current_alerts
        time.sleep(60)

if __name__ == "__main__":
    main()
