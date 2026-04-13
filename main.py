"""
Science Bot — Main Entry Point
================================
Scientific Content Monitor & Forwarder for Telegram Channels.

Usage:
    python main.py

Requirements:
    pip install python-telegram-bot aiohttp python-dotenv
"""

import os
import logging
import asyncio
from telegram import BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)

from config import BOT_TOKEN, DATABASE_PATH
import database as db
from handlers import (
    cmd_start, cmd_help, cmd_stats, cmd_settings,
    cmd_myid, cmd_whoami, cmd_claim_owner, cmd_owner_info, cmd_broadcast,
    cmd_add_channel, cmd_remove_channel, cmd_list_channels, cmd_channel_stats,
    cmd_set_destination,
    cmd_add_platform, cmd_remove_platform, cmd_list_platforms,
    cmd_add_keyword, cmd_remove_keyword,
    cmd_add_admin, cmd_remove_admin,
    handle_channel_post,
    callback_handler,
)

# ─────────────────────────────────────────────────
#   Logging Setup
# ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Setup bot commands menu."""
    commands = [
        BotCommand("start",         "تشغيل البوت"),
        BotCommand("help",          "قائمة الأوامر"),
        BotCommand("myid",          "معرفتي ودوري في البوت"),
        BotCommand("whoami",        "بطاقة هويتي وصلاحياتي"),
        BotCommand("claimowner",    "تسجيل نفسك مالكاً للبوت"),
        BotCommand("stats",         "الإحصائيات الشاملة"),
        BotCommand("settings",      "لوحة الإعدادات"),
        BotCommand("addchannel",    "إضافة قناة للمراقبة"),
        BotCommand("removechannel", "إزالة قناة من المراقبة"),
        BotCommand("channels",      "عرض القنوات المراقبة"),
        BotCommand("chanstats",     "إحصائيات قناة محددة"),
        BotCommand("setdest",       "تعيين قناة الوجهة"),
        BotCommand("addplatform",   "إضافة منصة خارجية"),
        BotCommand("removeplatform","إزالة منصة خارجية"),
        BotCommand("platforms",     "عرض المنصات"),
        BotCommand("addkeyword",    "إضافة كلمة مفتاحية"),
        BotCommand("removekeyword", "حذف كلمة مفتاحية"),
        BotCommand("addadmin",      "إضافة مشرف للبوت"),
        BotCommand("removeadmin",   "إزالة مشرف من البوت"),
        BotCommand("broadcast",     "إشعار لجميع المشرفين (مالك)"),
        BotCommand("ownerinfo",     "معلومات الملكية (مالك)"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands registered successfully.")


def main():
    # ── Init database ──
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    db.init_db()
    logger.info("Database initialized.")

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN not set! Please add it to your .env file.")
        return

    # ── Build Application ──
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # ── Register Handlers ──

    # Core commands
    application.add_handler(CommandHandler("start",          cmd_start))
    application.add_handler(CommandHandler("help",           cmd_help))
    application.add_handler(CommandHandler("stats",          cmd_stats))
    application.add_handler(CommandHandler("settings",       cmd_settings))

    # Owner / Identity commands
    application.add_handler(CommandHandler("myid",           cmd_myid))
    application.add_handler(CommandHandler("whoami",         cmd_whoami))
    application.add_handler(CommandHandler("claimowner",     cmd_claim_owner))
    application.add_handler(CommandHandler("ownerinfo",      cmd_owner_info))
    application.add_handler(CommandHandler("broadcast",      cmd_broadcast))

    # Channel management
    application.add_handler(CommandHandler("addchannel",     cmd_add_channel))
    application.add_handler(CommandHandler("removechannel",  cmd_remove_channel))
    application.add_handler(CommandHandler("channels",       cmd_list_channels))
    application.add_handler(CommandHandler("chanstats",      cmd_channel_stats))

    # Destination
    application.add_handler(CommandHandler("setdest",        cmd_set_destination))

    # External platforms
    application.add_handler(CommandHandler("addplatform",    cmd_add_platform))
    application.add_handler(CommandHandler("removeplatform", cmd_remove_platform))
    application.add_handler(CommandHandler("platforms",      cmd_list_platforms))

    # Keywords
    application.add_handler(CommandHandler("addkeyword",     cmd_add_keyword))
    application.add_handler(CommandHandler("removekeyword",  cmd_remove_keyword))

    # Admins
    application.add_handler(CommandHandler("addadmin",       cmd_add_admin))
    application.add_handler(CommandHandler("removeadmin",    cmd_remove_admin))

    # Inline keyboard callbacks
    application.add_handler(CallbackQueryHandler(callback_handler))

    # ── Channel Post Handler (ALL media types) ──
    application.add_handler(
        MessageHandler(filters.ChatType.CHANNEL, handle_channel_post)
    )

    # ── Start Polling ──
    logger.info("🚀 Science Bot is starting...")
    application.run_polling(
        allowed_updates=["message", "channel_post", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
