import asyncio
import os

from .core import TelegramBot
from .logger import setup_log


async def main():
    setup_log()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Set BOT_TOKEN in environment variable BOT_TOKEN")
    bot = TelegramBot(token=token, modules_package="bot.modules")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
