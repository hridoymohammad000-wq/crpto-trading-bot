import asyncio
import os
from dotenv import load_dotenv

load_dotenv("app/backend/.env")

from app.main import activity_service

async def main():
    print("Syncing closed trades...")
    count = await activity_service.sync_closed_trades()
    print(f"Synced {count} trades")

if __name__ == "__main__":
    asyncio.run(main())
