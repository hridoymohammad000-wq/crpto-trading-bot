import asyncio
from app.exchange.bybit import BybitDemoClient
from app.core.config import settings
async def test():
    c = BybitDemoClient(settings)
    ts = await c.fetch_all_tickers()
    print([(t.symbol, t.turnover_24h) for t in ts if t.symbol == 'BTCUSDT'])
    await c.close()
asyncio.run(test())
