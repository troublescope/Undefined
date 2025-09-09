from telegram import Update
from telegram.ext import CallbackContext

from ..core import command, on_load, on_start


@on_load
async def loaded(bot, *_):
    bot.log.info("ping module loaded")


@on_start
async def started(bot, *_):
    bot.log.info("bot started; ping ready")


@command("ping")
async def ping(bot, update: Update, ctx: CallbackContext):
    await update.effective_message.reply_text("pong")


@command("start")
async def start(bot, update: Update, ctx: CallbackContext):
    await update.effective_message.reply_text("Hi. Send /ping")
