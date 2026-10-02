import json
import re

with open('trades.json', encoding='utf-8') as f:
    trades = json.load(f)[:21]

print("# | Symbol | Side | PnL | Exit Reason | MAE-R | MFE-R | SL/ATR | Status | Root Cause")
for i, t in enumerate(trades, 1):
    sym = t.get('symbol', '')[:10]
    side = t.get('side', '')
    pnl = float(t.get('realized_pnl') or 0)
    pnl_str = f"{pnl:.2f}"
    reason = str(t.get('exit_reason'))[:15]
    
    mae_r = t.get('mae_r')
    mfe_r = t.get('mfe_r')
    sl_atr = t.get('sl_distance_atr')
    status = t.get('excursion_status')
    cause = t.get('root_cause')
    
    mae_str = f"{float(mae_r):.2f}" if mae_r is not None else "NULL"
    mfe_str = f"{float(mfe_r):.2f}" if mfe_r is not None else "NULL"
    sl_atr_str = f"{float(sl_atr):.2f}" if sl_atr is not None else "NULL"
    status_str = str(status)
    cause_str = str(cause)
    
    print(f"{i} | {sym} | {side} | {pnl_str} | {reason} | {mae_str} | {mfe_str} | {sl_atr_str} | {status_str} | {cause_str}")

# Stats
losing = [t for t in trades if float(t.get('realized_pnl') or 0) < 0]
complete = sum(1 for t in losing if t.get('excursion_status') == 'COMPLETE')
partial = sum(1 for t in losing if t.get('excursion_status') == 'PARTIAL')
unknown = sum(1 for t in losing if t.get('excursion_status') in ('HISTORICAL_DATA_UNAVAILABLE', None))

mfe_high = sum(1 for t in losing if t.get('mfe_r') is not None and float(t.get('mfe_r')) >= 0.5)
mfe_low = sum(1 for t in losing if t.get('mfe_r') is not None and float(t.get('mfe_r')) < 0.2)
sl_tight = sum(1 for t in losing if t.get('sl_distance_atr') is not None and float(t.get('sl_distance_atr')) < 0.75)

aligned_1h = 0
adx_high = 0
rvol_high = 0

for t in losing:
    ev = str(t.get('root_cause_evidence') or '') + str(t.get('diagnostic_reason') or '')
    
    # 1H Aligned means HTF EMA Fast > HTF EMA Slow for LONG, and < for SHORT
    # But usually it says "1H trend aligned: yes" or we parse HTF values
    # Let's extract HTF_EMA_fast and HTF_EMA_slow
    fast_m = re.search(r'HTF_EMA_fast=([0-9.]+)', ev)
    slow_m = re.search(r'HTF_EMA_slow=([0-9.]+)', ev)
    if fast_m and slow_m:
        fast = float(fast_m.group(1))
        slow = float(slow_m.group(1))
        if t.get('side') == 'LONG' and fast > slow:
            aligned_1h += 1
        elif t.get('side') == 'SHORT' and fast < slow:
            aligned_1h += 1
            
    adx_m = re.search(r'ADX=([0-9.]+)', ev)
    if adx_m and float(adx_m.group(1)) >= 25:
        adx_high += 1
        
    vol_m = re.search(r'volume_ratio=([0-9.]+)', ev)
    if vol_m and float(vol_m.group(1)) >= 1.2:
        rvol_high += 1

print("\n--- STATS ---")
print(f"1. How many losses? {len(losing)}")
print(f"2. How many have COMPLETE MAE/MFE? {complete}")
print(f"3. How many are PARTIAL? {partial}")
print(f"4. How many are UNKNOWN? {unknown}")
print(f"5. For the losing trades, how many had MFE >= 0.5R before SL? {mfe_high}")
print(f"6. How many had MFE < 0.2R? {mfe_low}")
print(f"7. How many had SL/ATR < 0.75? {sl_tight}")
print(f"8. How many had 1H aligned? {aligned_1h}")
print(f"9. How many had ADX >= 25? {adx_high}")
print(f"10. How many had RVOL >= 1.2? {rvol_high}")
