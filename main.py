"""
main.py  –  Entry point for NexusHost
Run: python main.py
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# ── Logging setup ──────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)

from bot import Bot


async def main():
    token = os.getenv("TOKEN")
    if not token:
        raise RuntimeError("TOKEN not set in .env!")
    async with Bot() as bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
