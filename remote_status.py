import sys
import time
import requests
from datetime import datetime, timezone

def format_duration(seconds: float | None) -> str:
    if not seconds:
        return "N/A"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"

def main() -> None:
    try:
        health_resp = requests.get("http://localhost:8000/health", timeout=5)
        health_resp.raise_for_status()
        health = health_resp.json()
    except Exception as e:
        print(f"Error connecting to backend: {e}")
        return

    try:
        account_resp = requests.get("http://localhost:8000/account/summary", timeout=5)
        account_resp.raise_for_status()
        account = account_resp.json()
    except Exception as e:
        print(f"Error fetching account data: {e}")
        account = {}

    print("="*40)
    print("REMOTE OBSERVATION DASHBOARD")
    print("="*40)
    
    bot_status = health.get("bot_status", "UNKNOWN")
    print(f"BOT STATUS     : {bot_status}")
    print(f"Uptime         : {format_duration(health.get('uptime_seconds'))}")
    print(f"Backend        : {'HEALTHY' if health.get('backend_healthy') else 'UNHEALTHY'}")
    print(f"Bybit          : {'CONNECTED' if health.get('bybit_connected') else 'DISCONNECTED'}")
    print(f"DB             : {'HEALTHY' if health.get('db_healthy') else 'UNHEALTHY'}")
    print(f"Scanner        : {'RUNNING' if health.get('scanner_running') else 'STOPPED'}")
    
    last_scan = health.get("last_scan_at")
    last_scan_str = last_scan if last_scan else "N/A"
    print(f"Last Scan      : {last_scan_str}")
    
    open_pos = health.get("open_positions", 0)
    print(f"Open Positions : {open_pos}")
    
    pm_running = health.get("position_manager_running", False)
    print(f"BE Manager     : {'ACTIVE' if pm_running else 'INACTIVE'}")
    
    # Errors 24h might not be precisely tracked, we can just show if there are critical errors
    crits = [k for k, v in health.get("critical_states", {}).items() if v]
    crits_str = ", ".join(crits) if crits else "None"
    print(f"Critical States: {crits_str}")
    
    print("-" * 40)
    print(f"Balance        : {account.get('balance', 'N/A')}")
    print(f"Equity         : {account.get('equity', 'N/A')}")
    print(f"Available      : {account.get('availableBalance', 'N/A')}")
    print(f"Used Margin    : {account.get('margin_used', 'N/A')}")
    print("="*40)

if __name__ == "__main__":
    while True:
        # Clear screen
        print("\033[H\033[J", end="")
        main()
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            break
