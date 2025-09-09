import asyncio
import os

from core import TelegramBot
from logger import setup_log


async def main():
    setup_log()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Set BOT_TOKEN in env")
    bot = TelegramBot(token=token, modules_package="modules")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
