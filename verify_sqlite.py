import sqlite3
from decimal import Decimal

def main():
    conn = sqlite3.connect('app/backend/bot.sqlite')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM closed_trades ORDER BY updated_at DESC LIMIT 50")
    data = [dict(row) for row in cursor.fetchall()]
    
    losing_trades = [t for t in data if float(t.get('realized_pnl') or 0) < 0]
    print(f'Total trades: {len(data)}, Losing trades: {len(losing_trades)}')

    print('\n--- VERIFICATION OF LOSING TRADES ---')
    for t in losing_trades[:5]: 
        print(f'Symbol: {t.get("symbol")}')
        print(f'Side: {t.get("side")}')
        print(f'Entry: {t.get("entry_price")}')
        print(f'Exit: {t.get("exit_price")}')
        print(f'SL: {t.get("stop_loss")}')
        print(f'TP: {t.get("take_profit")}')
        print(f'PnL: {t.get("realized_pnl")}')
        print(f'Exit Reason: {t.get("exit_reason")}')
        print(f'Root Cause: {t.get("root_cause")}')
        print(f'Excursion Status: {t.get("excursion_status")}')
        print(f'MAE Price: {t.get("mae_price")}')
        print(f'MFE Price: {t.get("mfe_price")}')
        print(f'MAE Pct: {t.get("mae_pct")}')
        print(f'MFE Pct: {t.get("mfe_pct")}')
        print(f'MAE R: {t.get("mae_r")}')
        print(f'MFE R: {t.get("mfe_r")}')
        print(f'SL Distance: {t.get("sl_distance")}')
        print(f'SL Dist / ATR: {t.get("sl_distance_atr")}')
        print(f'MAE At: {t.get("mae_at")}')
        print(f'MFE At: {t.get("mfe_at")}')
        print(f'Root Cause Evidence: {t.get("root_cause_evidence")}')
        print('-' * 20)

    print("\n--- COMPACT TABLE (Last 21 trades) ---")
    print(f"{'SL':<5} | {'Symbol':<10} | {'PnL':<8} | {'MAE-R':<8} | {'MFE-R':<8} | {'SL/ATR':<6} | {'Status':<15} | {'Root Cause'}")
    count_mae = 0
    count_no_mae = 0
    count_complete = 0
    count_partial = 0
    count_hist_unavail = 0

    for t in data[:21]:
        sl = 'Y' if t.get('exit_reason') == 'LIKELY_SL_HIT' else 'N'
        sym = t.get('symbol', '')[:10]
        pnl = float(t.get('realized_pnl') or 0)
        pnl_str = f"{pnl:.2f}"
        mae_r = t.get('mae_r')
        mfe_r = t.get('mfe_r')
        sl_atr = t.get('sl_distance_atr')
        status = t.get('excursion_status')
        root_cause = t.get('root_cause')

        if mae_r is not None:
            count_mae += 1
        else:
            count_no_mae += 1
            
        if status == 'COMPLETE':
            count_complete += 1
        elif status == 'PARTIAL':
            count_partial += 1
        else:
            count_hist_unavail += 1
            
        mae_str = f"{float(mae_r):.2f}" if mae_r is not None else "NULL"
        mfe_str = f"{float(mfe_r):.2f}" if mfe_r is not None else "NULL"
        sl_atr_str = f"{float(sl_atr):.2f}" if sl_atr is not None else "NULL"
        status_str = str(status)[:15]
        cause_str = str(root_cause)[:30]
        
        print(f"{sl:<5} | {sym:<10} | {pnl_str:<8} | {mae_str:<8} | {mfe_str:<8} | {sl_atr_str:<6} | {status_str:<15} | {cause_str}")

    print("\nREAL DATA VERIFICATION")
    print("----------------------")
    print(f"Trades inspected: {min(21, len(data))}")
    print(f"Trades with MAE/MFE: {count_mae}")
    print(f"Trades without MAE/MFE: {count_no_mae}")
    print(f"COMPLETE: {count_complete}")
    print(f"PARTIAL: {count_partial}")
    print(f"HISTORICAL_DATA_UNAVAILABLE: {count_hist_unavail}")

if __name__ == "__main__":
    main()
