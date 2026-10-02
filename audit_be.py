import json

with open('trades.json', encoding='utf-8') as f:
    trades = json.load(f)[:21]

print("Symbol | Entry | Original SL | MFE_R | Reached +1R? | BE expected? | Actual exit | Actual exit reason | BE status | Failure reason")

losing_trades = [t for t in trades if float(t.get('realized_pnl') or 0) < 0]

for t in losing_trades:
    sym = t.get('symbol', '')[:10]
    entry = float(t.get('entry_price') or 0)
    sl = float(t.get('stop_loss') or 0) if t.get('stop_loss') is not None else None
    mfe_r = float(t.get('mfe_r')) if t.get('mfe_r') is not None else None
    exit_price = float(t.get('exit_price') or 0)
    reason = str(t.get('exit_reason'))[:15]
    
    if mfe_r is None:
        continue

    reached_1r = "Yes" if mfe_r >= 1.0 else "No"
    be_expected = "Yes" if mfe_r >= 1.0 else "No"
    
    be_status = ""
    failure_reason = ""
    
    if mfe_r < 1.0:
        be_status = "BE_TRIGGER_NOT_REACHED"
    else:
        # Reached +1R
        # check if it closed at original SL or break-even
        # Original SL loss usually means it lost ~ 1R. Let's see if exit_price is near sl or near entry.
        # It's a losing trade, so it lost money.
        # Break-even might still lose a tiny bit due to fees.
        # But if it lost 1R, then exit_price is near SL.
        dist_to_sl = abs(exit_price - sl) if sl else 9999
        dist_to_entry = abs(exit_price - entry)
        
        if dist_to_sl < dist_to_entry:
            be_status = "BE_MANAGEMENT_FAILURE"
            failure_reason = "Closed near full SL despite reaching +1R"
        else:
            be_status = "BE_WORKED"
            failure_reason = "Closed near BE (fees caused slight loss)"
            
    # formatting
    mfe_r_str = f"{mfe_r:.2f}"
    entry_str = f"{entry}"
    sl_str = f"{sl}"
    exit_str = f"{exit_price}"
    
    print(f"{sym} | {entry_str} | {sl_str} | {mfe_r_str} | {reached_1r} | {be_expected} | {exit_str} | {reason} | {be_status} | {failure_reason}")
