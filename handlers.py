"""
Bot Handlers
============
All Telegram bot command and callback handlers.
"""

import logging
import aiohttp
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, Bot
)
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

import database as db
from classifier import classify_content, get_media_type, get_message_text
from config import BOT_VERSION, FORWARD_TEMPLATE, ADMIN_IDS, OWNER_ID

logger = logging.getLogger(__name__)

ARABIC_MONTHS = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
]

WEEKDAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

MEDIA_TYPE_AR = {
    "text": "📝 نص",
    "photo": "🖼️ صورة",
    "video": "🎥 فيديو",
    "document": "📄 مستند",
    "audio": "🎵 صوت",
    "animation": "🎞️ متحرك",
    "other": "📎 مرفق",
}


# ════════════════════════════════════════════════
#   Permission Helpers
# ════════════════════════════════════════════════

def is_owner(user_id: int) -> bool:
    """Check if user is the bot owner (highest privilege)."""
    # Owner from .env file
    if OWNER_ID and user_id == OWNER_ID:
        return True
    # Owner stored in database (set via /claimowner)
    db_owner = db.get_setting("owner_id", "")
    return db_owner != "" and str(user_id) == db_owner


def is_admin(user_id: int) -> bool:
    """Check if user is an admin OR the owner."""
    if is_owner(user_id):
        return True
    all_admins = set(ADMIN_IDS) | set(db.get_bot_admins())
    return user_id in all_admins


def get_role_label(user_id: int) -> str:
    """Return Arabic role label for a user."""
    if is_owner(user_id):
        return "👑 مالك البوت"
    if user_id in set(ADMIN_IDS):
        return "⭐ مشرف رئيسي"
    if user_id in set(db.get_bot_admins()):
        return "🔧 مشرف"
    return "👤 مستخدم عادي"


def format_arabic_date(dt: datetime) -> tuple:
    """Format datetime to Arabic date and time strings."""
    day_name = WEEKDAYS_AR[dt.weekday()]
    month_name = ARABIC_MONTHS[dt.month]
    date_str = f"{day_name}، {dt.day} {month_name} {dt.year}"
    time_str = dt.strftime("%I:%M %p").replace("AM", "ص").replace("PM", "م")
    return date_str, time_str


def format_number(n: int) -> str:
    """Format number with Arabic thousands separator."""
    return f"{n:,}".replace(",", "،")


# ════════════════════════════════════════════════
#   /start  &  /help
# ════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    role = get_role_label(uid)

    # ── Check if bot has no owner yet → prompt to claim ──
    db_owner = db.get_setting("owner_id", "")
    no_owner_yet = (not OWNER_ID or OWNER_ID == 0) and db_owner == ""

    if no_owner_yet:
        text = (
            f"🔬 *مرحباً {user.first_name}!*\n\n"
            "⚠️ *البوت لا يزال بدون مالك!*\n\n"
            "إذا كنت صاحب هذا البوت، أرسل:\n"
            "`/claimowner` لتسجيل نفسك مالكاً\n\n"
            f"🆔 معرفك: `{uid}`"
        )
    else:
        owner_badge = "👑 " if is_owner(uid) else ""
        text = (
            f"🔬 *مرحباً {owner_badge}{user.first_name}!*\n"
            f"🎭 صلاحيتك: {role}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "أنا بوت المحتوى العلمي المتطور 🤖\n"
            "أقوم بـ:\n"
            "• 🔍 رصد المحتوى العلمي في القنوات\n"
            "• 📤 تحويل المحتوى تلقائياً للقناة المحددة\n"
            "• 📊 إحصائيات شاملة ومفصّلة\n"
            "• 🌐 إرسال المحتوى للمنصات الخارجية\n\n"
            "اضغط /help لعرض الأوامر المتاحة\n"
            f"🆔 معرفك: `{uid}`"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   /myid — Show User ID
# ════════════════════════════════════════════════
async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the user their Telegram ID and role."""
    user = update.effective_user
    uid = user.id
    role = get_role_label(uid)

    username_str = f"@{user.username}" if user.username else "بدون يوزرنيم"

    text = (
        "🪪 *معلوماتك في البوت*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 الاسم: *{user.full_name}*\n"
        f"📛 اليوزرنيم: {username_str}\n"
        f"🆔 معرفك: `{uid}`\n"
        f"🎭 صلاحيتك: {role}\n\n"
        "💡 انسخ معرفك واضفه في ملف `.env`\n"
        "كقيمة `OWNER_ID` أو `ADMIN_IDS`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   /whoami — Full Identity Card
# ════════════════════════════════════════════════
async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows full identity card with permissions."""
    user = update.effective_user
    uid = user.id
    role = get_role_label(uid)
    owner = is_owner(uid)
    admin = is_admin(uid)

    perms = []
    if owner:
        perms = [
            "✅ عرض الإحصائيات",
            "✅ إدارة القنوات",
            "✅ تغيير الإعدادات",
            "✅ إضافة/حذف المشرفين",
            "✅ إضافة المنصات الخارجية",
            "✅ إرسال إشعار للجميع",
            "✅ إيقاف/تشغيل البوت",
            "✅ جميع الصلاحيات",
        ]
    elif admin:
        perms = [
            "✅ عرض الإحصائيات",
            "✅ إدارة القنوات",
            "✅ تغيير الإعدادات",
            "✅ إضافة المنصات الخارجية",
            "❌ إضافة/حذف المشرفين",
            "❌ إيقاف/تشغيل البوت",
        ]
    else:
        perms = [
            "❌ لا توجد صلاحيات إدارية",
            "💡 تواصل مع المالك للحصول على صلاحيات",
        ]

    perms_text = "\n".join(f"  {p}" for p in perms)
    text = (
        f"🪪 *بطاقة الهوية — {user.full_name}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 المعرف: `{uid}`\n"
        f"🎭 الدور: {role}\n\n"
        f"📋 *الصلاحيات:*\n{perms_text}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   /claimowner — First-Run Owner Setup
# ════════════════════════════════════════════════
async def cmd_claim_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows the first user to claim ownership (only if no owner is set)."""
    user = update.effective_user
    uid = user.id

    # If already has an owner
    existing_owner = db.get_setting("owner_id", "")
    if (OWNER_ID and OWNER_ID != 0) or existing_owner:
        # If current user IS the owner, show info
        if is_owner(uid):
            await update.message.reply_text(
                f"👑 *أنت بالفعل مالك هذا البوت!*\n\n"
                f"🆔 معرفك: `{uid}`",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "⛔ *البوت لديه مالك بالفعل.*\n"
                "لا يمكنك المطالبة بالملكية.",
                parse_mode=ParseMode.MARKDOWN
            )
        return

    # Set this user as owner
    db.set_setting("owner_id", str(uid))
    db.set_setting("owner_name", user.full_name)
    db.add_bot_admin(uid, user.username or "")

    text = (
        "👑 *تهانينا! لقد أصبحت مالك هذا البوت*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 الاسم: {user.full_name}\n"
        f"🆔 المعرف: `{uid}`\n\n"
        "🔒 *لتأمين ملكيتك بشكل دائم:*\n"
        "أضف هذا السطر في ملف `.env`:\n"
        f"`OWNER_ID={uid}`\n\n"
        "✅ الآن لديك صلاحيات كاملة على البوت.\n"
        "اضغط /settings لبدء الإعداد."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    logger.info(f"Owner claimed by user {uid} ({user.full_name})")


# ════════════════════════════════════════════════
#   /broadcast — Owner Only
# ════════════════════════════════════════════════
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a broadcast message to all bot admins (owner only)."""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ الاستخدام: `/broadcast <الرسالة>`\n\n"
            "مثال: `/broadcast تم تحديث البوت للإصدار 2.1`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    msg = " ".join(context.args)
    admins = list(set(ADMIN_IDS) | set(db.get_bot_admins()))
    sent = 0
    failed = 0

    for admin_id in admins:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📢 *رسالة من المالك:*\n\n{msg}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent += 1
        except TelegramError:
            failed += 1

    await update.message.reply_text(
        f"✅ *تم الإرسال*\n"
        f"📤 نجح: {sent} | ❌ فشل: {failed}",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    owner = is_owner(uid)
    admin = is_admin(uid)

    # Base commands for everyone
    text = (
        "📖 *قائمة الأوامر*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🆔 *معرفتي وصلاحيتي:*\n"
        "├ /myid — اعرف معرفك ودورك\n"
        "└ /whoami — بطاقة هويتك الكاملة\n\n"
    )

    if admin:
        text += (
            "🔧 *الأوامر الأساسية:*\n"
            "├ /start — تشغيل البوت\n"
            "├ /stats — الإحصائيات الشاملة\n"
            "└ /settings — لوحة الإعدادات\n\n"
            "📢 *إدارة القنوات:*\n"
            "├ /addchannel `<معرف>` — إضافة قناة\n"
            "├ /removechannel `<معرف>` — إزالة قناة\n"
            "├ /channels — قائمة القنوات\n"
            "└ /chanstats `<معرف>` — إحصائيات قناة\n\n"
            "🎯 *إعداد الوجهة:*\n"
            "└ /setdest `<معرف>` — قناة الوجهة\n\n"
            "🌐 *المنصات الخارجية:*\n"
            "├ /addplatform `<اسم>` `<رابط>` — إضافة منصة\n"
            "├ /removeplatform `<اسم>` — إزالة منصة\n"
            "└ /platforms — قائمة المنصات\n\n"
            "🔑 *الكلمات المفتاحية:*\n"
            "├ /addkeyword `<كلمة>` — إضافة كلمة\n"
            "└ /removekeyword `<كلمة>` — حذف كلمة\n\n"
            "👥 *المشرفون:*\n"
            "├ /addadmin `<معرف>` — إضافة مشرف\n"
            "└ /removeadmin `<معرف>` — إزالة مشرف\n"
        )

    if owner:
        text += (
            "\n👑 *أوامر المالك الحصرية:*\n"
            "├ /broadcast `<رسالة>` — إشعار للجميع\n"
            "└ /ownerinfo — معلومات الملكية\n"
        )

    if not admin:
        text += (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ ليس لديك صلاحيات إدارية.\n"
            "تواصل مع مالك البوت للحصول عليها."
        )

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   /ownerinfo — Owner Information (Owner Only)
# ════════════════════════════════════════════════
async def cmd_owner_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed ownership info — owner only."""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("⛔ هذا الأمر للمالك فقط.")
        return

    uid = update.effective_user.id
    db_owner = db.get_setting("owner_id", "لم يُحدد")
    owner_name = db.get_setting("owner_name", "غير معروف")
    env_owner = str(OWNER_ID) if OWNER_ID else "غير محدد في .env"
    admins = list(set(ADMIN_IDS) | set(db.get_bot_admins()))
    stats = db.get_global_stats()

    text = (
        "👑 *لوحة المالك — معلومات شاملة*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔐 *بيانات الملكية:*\n"
        f"├ المالك الحالي: `{uid}`\n"
        f"├ الاسم: {owner_name}\n"
        f"├ في قاعدة البيانات: `{db_owner}`\n"
        f"└ في ملف .env: `{env_owner}`\n\n"
        f"👥 *المشرفون:* {len(admins)} مشرف\n"
        f"📢 *القنوات المراقبة:* {stats['total_channels']}\n"
        f"🔬 *المحتوى العلمي الكلي:* {format_number(stats['scientific_posts'])}\n"
        f"🌐 *المنصات الخارجية:* {stats['platforms_count']}\n\n"
        "🔒 *التوصية الأمنية:*\n"
        f"أضف هذا السطر في `.env`:\n`OWNER_ID={uid}`\n"
        "لضمان بقاء ملكيتك حتى بعد إعادة تشغيل البوت."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   /stats — Global Statistics
# ════════════════════════════════════════════════
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    stats = db.get_global_stats()
    channels = db.get_all_channels()
    destination = db.get_setting("destination_channel", "غير محدد")

    # Calculate rate
    rate = 0
    if stats["total_posts"] > 0:
        rate = round((stats["scientific_posts"] / stats["total_posts"]) * 100, 1)

    text = (
        "📊 *الإحصائيات الشاملة*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📢 *القنوات المراقبة:* {format_number(stats['total_channels'])}\n"
        f"🎯 *قناة الوجهة:* `{destination}`\n"
        f"🌐 *المنصات الخارجية:* {stats['platforms_count']}\n\n"
        "📈 *إحصائيات المحتوى:*\n"
        f"├ إجمالي المنشورات: {format_number(stats['total_posts'])}\n"
        f"├ المحتوى العلمي: {format_number(stats['scientific_posts'])}\n"
        f"├ نسبة العلمي: {rate}%\n"
        f"├ الفيديوهات: {format_number(stats['total_videos'])}\n"
        f"├ الصور: {format_number(stats['total_images'])}\n"
        f"├ المستندات: {format_number(stats['total_docs'])}\n"
        f"└ منشورات اليوم: {format_number(stats['today_count'])}\n\n"
        f"📤 *أُرسل للمنصات:* {format_number(stats['platforms_sent'])}\n"
    )

    # Top channels summary
    if channels:
        text += "\n🏆 *أنشط القنوات:*\n"
        for ch in channels[:5]:
            ch_rate = 0
            if ch["total_posts"] > 0:
                ch_rate = round((ch["scientific_posts"] / ch["total_posts"]) * 100, 1)
            text += (
                f"• {ch['channel_name']}: "
                f"{format_number(ch['scientific_posts'])} علمي "
                f"({ch_rate}%)\n"
            )

    keyboard = [[InlineKeyboardButton("🔄 تحديث", callback_data="refresh_stats"),
                 InlineKeyboardButton("📋 تفاصيل", callback_data="detailed_stats")]]
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ════════════════════════════════════════════════
#   /settings — Settings Panel
# ════════════════════════════════════════════════
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await show_settings_menu(update.message.reply_text)


async def show_settings_menu(reply_func, edit=False):
    destination = db.get_setting("destination_channel", "غير محدد")
    threshold = db.get_setting("threshold", "2")
    channels_count = len(db.get_all_channels())
    platforms_count = len(db.get_all_platforms())

    text = (
        "⚙️ *لوحة الإعدادات*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 قناة الوجهة: `{destination}`\n"
        f"📢 القنوات المراقبة: {channels_count}\n"
        f"🌐 المنصات الخارجية: {platforms_count}\n"
        f"🎚️ حساسية الكشف: {threshold}/5\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("📢 إدارة القنوات", callback_data="menu_channels"),
            InlineKeyboardButton("🎯 قناة الوجهة", callback_data="menu_destination"),
        ],
        [
            InlineKeyboardButton("🌐 المنصات الخارجية", callback_data="menu_platforms"),
            InlineKeyboardButton("🔑 الكلمات المفتاحية", callback_data="menu_keywords"),
        ],
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="menu_stats"),
            InlineKeyboardButton("👥 المشرفون", callback_data="menu_admins"),
        ],
        [
            InlineKeyboardButton("🎚️ حساسية الكشف", callback_data="menu_threshold"),
            InlineKeyboardButton("ℹ️ حول البوت", callback_data="menu_about"),
        ],
    ]
    await reply_func(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ════════════════════════════════════════════════
#   Inline Keyboard Callbacks
# ════════════════════════════════════════════════
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.answer("⛔ غير مصرح لك بهذا الإجراء", show_alert=True)
        return

    data = query.data

    if data == "refresh_stats":
        stats = db.get_global_stats()
        rate = 0
        if stats["total_posts"] > 0:
            rate = round((stats["scientific_posts"] / stats["total_posts"]) * 100, 1)
        text = (
            f"📊 *الإحصائيات — محدّثة*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📢 القنوات: {stats['total_channels']}\n"
            f"📝 إجمالي: {format_number(stats['total_posts'])}\n"
            f"🔬 علمي: {format_number(stats['scientific_posts'])} ({rate}%)\n"
            f"🎥 فيديو: {format_number(stats['total_videos'])}\n"
            f"🖼️ صور: {format_number(stats['total_images'])}\n"
            f"📄 مستندات: {format_number(stats['total_docs'])}\n"
            f"📅 اليوم: {format_number(stats['today_count'])}\n"
        )
        keyboard = [[InlineKeyboardButton("🔄 تحديث", callback_data="refresh_stats")]]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data == "detailed_stats":
        channels = db.get_all_channels()
        text = "📋 *تفاصيل القنوات:*\n━━━━━━━━━━━━━━━━\n\n"
        for ch in channels:
            rate = 0
            if ch["total_posts"] > 0:
                rate = round((ch["scientific_posts"] / ch["total_posts"]) * 100, 1)
            text += (
                f"📢 *{ch['channel_name']}*\n"
                f"  ├ الكل: {format_number(ch['total_posts'])}\n"
                f"  ├ علمي: {format_number(ch['scientific_posts'])} ({rate}%)\n"
                f"  ├ فيديو: {format_number(ch['total_videos'])}\n"
                f"  └ صور: {format_number(ch['total_images'])}\n\n"
            )
        if not channels:
            text += "لا توجد قنوات مراقبة بعد."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="refresh_stats")]]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data == "menu_channels":
        channels = db.get_all_channels()
        text = f"📢 *القنوات المراقبة ({len(channels)})*\n━━━━━━━━━━━━━━━━\n\n"
        if channels:
            for ch in channels:
                text += f"• `{ch['channel_id']}` — {ch['channel_name']}\n"
        else:
            text += "لا توجد قنوات مضافة بعد.\n"
        text += "\n➕ لإضافة قناة: `/addchannel <معرف_القناة>`\n"
        text += "➖ لإزالة قناة: `/removechannel <معرف_القناة>`"
        keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_settings")]]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data == "menu_destination":
        destination = db.get_setting("destination_channel", "غير محدد")
        text = (
            f"🎯 *قناة الوجهة الحالية:*\n`{destination}`\n\n"
            "لتغييرها أرسل:\n"
            "`/setdest <معرف_القناة>`\n\n"
            "💡 *ملاحظة:* يجب أن يكون البوت مشرفاً في قناة الوجهة\n"
            "وأن تمنحه صلاحية إرسال الرسائل."
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_settings")]]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data == "menu_platforms":
        platforms = db.get_all_platforms()
        text = f"🌐 *المنصات الخارجية ({len(platforms)})*\n━━━━━━━━━━━━━━━━\n\n"
        if platforms:
            for p in platforms:
                text += (
                    f"• *{p['name']}*\n"
                    f"  النوع: {p['platform_type']}\n"
                    f"  أُرسل: {p['posts_sent']} منشور\n\n"
                )
        else:
            text += "لا توجد منصات مضافة بعد.\n"
        text += "\n➕ لإضافة منصة:\n`/addplatform <اسم> <رابط_webhook>`"
        keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_settings")]]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data == "menu_keywords":
        keywords = db.get_custom_keywords()
        text = f"🔑 *الكلمات المفتاحية المخصصة ({len(keywords)})*\n━━━━━━━━━━━━━━━━\n\n"
        if keywords:
            for kw in keywords[:20]:
                text += f"• `{kw['keyword']}` (وزن: {kw['weight']})\n"
        else:
            text += "لا توجد كلمات مخصصة.\n"
        text += "\n➕ لإضافة كلمة: `/addkeyword <كلمة>`"
        keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_settings")]]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data == "menu_admins":
        admins = db.get_bot_admins()
        all_admins = list(set(ADMIN_IDS) | set(admins))
        text = f"👥 *مشرفو البوت ({len(all_admins)})*\n━━━━━━━━━━━━━━━━\n\n"
        for aid in all_admins:
            prefix = "⭐ " if aid in ADMIN_IDS else "👤 "
            text += f"{prefix}`{aid}`\n"
        text += "\n➕ `/addadmin <معرف>` | ➖ `/removeadmin <معرف>`"
        keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_settings")]]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data == "menu_threshold":
        current = db.get_setting("threshold", "2")
        text = (
            f"🎚️ *حساسية الكشف عن المحتوى العلمي*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"القيمة الحالية: *{current}*\n\n"
            "اختر مستوى الحساسية:"
        )
        keyboard = [
            [
                InlineKeyboardButton("1 — منخفض جداً", callback_data="set_threshold_1"),
                InlineKeyboardButton("2 — منخفض", callback_data="set_threshold_2"),
            ],
            [
                InlineKeyboardButton("3 — متوسط ✅", callback_data="set_threshold_3"),
                InlineKeyboardButton("4 — عالي", callback_data="set_threshold_4"),
            ],
            [
                InlineKeyboardButton("5 — عالي جداً", callback_data="set_threshold_5"),
                InlineKeyboardButton("🔙 رجوع", callback_data="back_settings"),
            ],
        ]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data.startswith("set_threshold_"):
        val = data.split("_")[-1]
        db.set_setting("threshold", val)
        await query.answer(f"✅ تم تحديد الحساسية إلى {val}", show_alert=True)
        await show_settings_inline(query)

    elif data == "menu_stats":
        await query.message.reply_text("/stats")

    elif data == "menu_about":
        text = (
            f"🤖 *بوت المحتوى العلمي*\n"
            f"الإصدار: {BOT_VERSION}\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔬 يرصد ويصنّف المحتوى العلمي\n"
            "📤 يحوّل المنشورات لقناة الوجهة\n"
            "🌐 يرسل للمنصات الخارجية\n"
            "📊 يوفر إحصائيات شاملة\n"
            "🔑 يدعم كلمات مفتاحية مخصصة\n"
            "🌍 يدعم العربية والإنجليزية"
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع للإعدادات", callback_data="back_settings")]]
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except TelegramError:
            pass

    elif data == "back_settings":
        await show_settings_inline(query)


async def show_settings_inline(query):
    """Re-render the settings menu in the same message."""
    destination = db.get_setting("destination_channel", "غير محدد")
    threshold = db.get_setting("threshold", "2")
    channels_count = len(db.get_all_channels())
    platforms_count = len(db.get_all_platforms())

    text = (
        "⚙️ *لوحة الإعدادات*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 قناة الوجهة: `{destination}`\n"
        f"📢 القنوات المراقبة: {channels_count}\n"
        f"🌐 المنصات الخارجية: {platforms_count}\n"
        f"🎚️ حساسية الكشف: {threshold}/5\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("📢 إدارة القنوات", callback_data="menu_channels"),
            InlineKeyboardButton("🎯 قناة الوجهة", callback_data="menu_destination"),
        ],
        [
            InlineKeyboardButton("🌐 المنصات الخارجية", callback_data="menu_platforms"),
            InlineKeyboardButton("🔑 الكلمات المفتاحية", callback_data="menu_keywords"),
        ],
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="menu_stats"),
            InlineKeyboardButton("👥 المشرفون", callback_data="menu_admins"),
        ],
        [
            InlineKeyboardButton("🎚️ حساسية الكشف", callback_data="menu_threshold"),
            InlineKeyboardButton("ℹ️ حول البوت", callback_data="menu_about"),
        ],
    ]
    try:
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except TelegramError:
        pass


# ════════════════════════════════════════════════
#   Channel Management Commands
# ════════════════════════════════════════════════
async def cmd_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "⚠️ الاستخدام: `/addchannel <معرف_القناة>`\n"
            "مثال: `/addchannel -100123456789`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    channel_id = context.args[0]
    try:
        chat = await context.bot.get_chat(channel_id)
        channel_name = chat.title or channel_id
        channel_link = f"https://t.me/{chat.username}" if chat.username else f"القناة: {channel_id}"

        db.add_channel(str(chat.id), channel_name, channel_link)
        await update.message.reply_text(
            f"✅ *تمت إضافة القناة بنجاح*\n\n"
            f"📢 الاسم: {channel_name}\n"
            f"🔗 الرابط: {channel_link}\n"
            f"🆔 المعرف: `{chat.id}`\n\n"
            "تأكد من إضافة البوت كمشرف في القناة.",
            parse_mode=ParseMode.MARKDOWN
        )
    except TelegramError as e:
        await update.message.reply_text(
            f"❌ *خطأ في إضافة القناة*\n`{e}`\n\n"
            "تأكد من:\n"
            "• صحة معرف القناة\n"
            "• أن البوت مشرف في القناة",
            parse_mode=ParseMode.MARKDOWN
        )


async def cmd_remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: `/removechannel <معرف_القناة>`",
                                         parse_mode=ParseMode.MARKDOWN)
        return

    channel_id = context.args[0]
    ch = db.get_channel(channel_id)
    if ch:
        db.remove_channel(channel_id)
        await update.message.reply_text(
            f"✅ تم إيقاف مراقبة القناة: *{ch['channel_name']}*",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("❌ القناة غير موجودة في قائمة المراقبة.")


async def cmd_list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    channels = db.get_all_channels()
    if not channels:
        await update.message.reply_text("📢 لا توجد قنوات مراقبة بعد.")
        return

    text = f"📢 *القنوات المراقبة ({len(channels)})*\n━━━━━━━━━━━━━━━━\n\n"
    for i, ch in enumerate(channels, 1):
        rate = 0
        if ch["total_posts"] > 0:
            rate = round((ch["scientific_posts"] / ch["total_posts"]) * 100, 1)
        text += (
            f"{i}. *{ch['channel_name']}*\n"
            f"   🆔 `{ch['channel_id']}`\n"
            f"   📊 {format_number(ch['scientific_posts'])}/{format_number(ch['total_posts'])} ({rate}%)\n\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_channel_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: `/chanstats <معرف_القناة>`",
                                         parse_mode=ParseMode.MARKDOWN)
        return

    ch = db.get_channel(context.args[0])
    if not ch:
        await update.message.reply_text("❌ القناة غير موجودة.")
        return

    rate = 0
    if ch["total_posts"] > 0:
        rate = round((ch["scientific_posts"] / ch["total_posts"]) * 100, 1)

    text = (
        f"📊 *إحصائيات: {ch['channel_name']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 المعرف: `{ch['channel_id']}`\n"
        f"🔗 الرابط: {ch['channel_link']}\n"
        f"📅 أُضيفت: {ch['added_at']}\n\n"
        f"📝 إجمالي المنشورات: {format_number(ch['total_posts'])}\n"
        f"🔬 المحتوى العلمي: {format_number(ch['scientific_posts'])}\n"
        f"📈 نسبة العلمي: {rate}%\n"
        f"🎥 الفيديوهات: {format_number(ch['total_videos'])}\n"
        f"🖼️ الصور: {format_number(ch['total_images'])}\n"
        f"📄 المستندات: {format_number(ch['total_docs'])}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   Destination Channel
# ════════════════════════════════════════════════
async def cmd_set_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "⚠️ الاستخدام: `/setdest <معرف_القناة>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    channel_id = context.args[0]
    try:
        chat = await context.bot.get_chat(channel_id)
        db.set_setting("destination_channel", str(chat.id))
        db.set_setting("destination_name", chat.title or channel_id)
        await update.message.reply_text(
            f"✅ *تم تعيين قناة الوجهة:*\n"
            f"📢 {chat.title}\n🆔 `{chat.id}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ خطأ: `{e}`", parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   External Platforms
# ════════════════════════════════════════════════
async def cmd_add_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ الاستخدام: `/addplatform <اسم> <رابط_webhook> [api_key]`\n\n"
            "مثال:\n`/addplatform موقعي https://mysite.com/webhook`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    name = context.args[0]
    url = context.args[1]
    api_key = context.args[2] if len(context.args) > 2 else ""

    db.add_platform(name, url, api_key)
    await update.message.reply_text(
        f"✅ *تمت إضافة المنصة:*\n"
        f"🌐 الاسم: {name}\n"
        f"🔗 الرابط: {url}",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_remove_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: `/removeplatform <اسم>`",
                                         parse_mode=ParseMode.MARKDOWN)
        return

    db.remove_platform(context.args[0])
    await update.message.reply_text(f"✅ تمت إزالة المنصة: {context.args[0]}")


async def cmd_list_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    platforms = db.get_all_platforms()
    if not platforms:
        await update.message.reply_text("🌐 لا توجد منصات مضافة.")
        return

    text = f"🌐 *المنصات الخارجية ({len(platforms)})*\n━━━━━━━━━━━━━━━━\n\n"
    for p in platforms:
        text += (
            f"• *{p['name']}*\n"
            f"  النوع: {p['platform_type']}\n"
            f"  أُرسل: {p['posts_sent']}\n"
            f"  الرابط: `{p['webhook_url']}`\n\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   Keywords Management
# ════════════════════════════════════════════════
async def cmd_add_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: `/addkeyword <كلمة>`",
                                         parse_mode=ParseMode.MARKDOWN)
        return

    kw = " ".join(context.args).lower()
    db.add_custom_keyword(kw)
    await update.message.reply_text(f"✅ تمت إضافة الكلمة المفتاحية: `{kw}`",
                                     parse_mode=ParseMode.MARKDOWN)


async def cmd_remove_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: `/removekeyword <كلمة>`",
                                         parse_mode=ParseMode.MARKDOWN)
        return

    kw = " ".join(context.args).lower()
    db.remove_custom_keyword(kw)
    await update.message.reply_text(f"✅ تم حذف الكلمة المفتاحية: `{kw}`",
                                     parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════
#   Admin Management
# ════════════════════════════════════════════════
async def cmd_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: `/addadmin <معرف_المستخدم>`",
                                         parse_mode=ParseMode.MARKDOWN)
        return

    try:
        uid = int(context.args[0])
        db.add_bot_admin(uid)
        await update.message.reply_text(f"✅ تمت إضافة المشرف: `{uid}`",
                                         parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ معرف غير صحيح.")


async def cmd_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("⚠️ الاستخدام: `/removeadmin <معرف_المستخدم>`",
                                         parse_mode=ParseMode.MARKDOWN)
        return

    try:
        uid = int(context.args[0])
        db.remove_bot_admin(uid)
        await update.message.reply_text(f"✅ تمت إزالة المشرف: `{uid}`",
                                         parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ معرف غير صحيح.")


# ════════════════════════════════════════════════
#   Channel Post Handler (Core Logic)
# ════════════════════════════════════════════════
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler for channel posts — classify and forward scientific content."""
    message = update.channel_post
    if not message:
        return

    channel_id = str(message.chat.id)
    channel_name = message.chat.title or channel_id
    channel_username = message.chat.username

    # Auto-register channel if not in DB
    channel = db.get_channel(channel_id)
    if not channel:
        channel_link = f"https://t.me/{channel_username}" if channel_username else f"t.me/c/{channel_id[4:]}"
        db.add_channel(channel_id, channel_name, channel_link)
        channel = db.get_channel(channel_id)
    else:
        # Update name/link if changed
        if channel["channel_name"] != channel_name:
            channel_link = f"https://t.me/{channel_username}" if channel_username else channel["channel_link"]
            db.update_channel_info(channel_id, channel_name, channel_link)
            channel = db.get_channel(channel_id)

    if not channel or not channel["is_active"]:
        return

    # Determine media type
    media_type = get_media_type(message)
    message_text = get_message_text(message)

    # Update channel stats
    db.increment_channel_stats(channel_id, is_scientific=False, media_type=media_type)

    # Classify content
    is_scientific, categories, keywords, hashtags, score = classify_content(message_text)

    if not is_scientific:
        return

    # Update scientific post count
    db.increment_channel_stats(channel_id, is_scientific=True, media_type="text")

    # Get destination channel
    destination = db.get_setting("destination_channel", "")
    if not destination:
        return

    # ── Format forwarding message ──
    now = message.date or datetime.utcnow()
    if hasattr(now, 'astimezone'):
        try:
            from datetime import timezone
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass

    date_str, time_str = format_arabic_date(now)
    channel_link = channel["channel_link"] or channel_id
    if channel_username:
        channel_link = f"https://t.me/{channel_username}"

    media_label = MEDIA_TYPE_AR.get(media_type, "📎 مرفق")
    categories_str = " | ".join(f"#{c}" for c in categories) if categories else "#علوم"

    header = FORWARD_TEMPLATE.format(
        channel_name=channel_name,
        channel_link=channel_link,
        date=date_str,
        time=time_str,
        categories=categories_str,
    )

    # Add score info for transparency
    header += f"🎯 *درجة الكشف:* {score} | نوع: {media_label}\n━━━━━━━━━━━━━━━━━━━━\n"

    forwarded_msg_id = None
    try:
        # Forward the original message first
        fwd = await context.bot.forward_message(
            chat_id=destination,
            from_chat_id=channel_id,
            message_id=message.message_id,
        )
        # Then send the metadata info
        await context.bot.send_message(
            chat_id=destination,
            text=header,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        forwarded_msg_id = fwd.message_id
    except TelegramError as e:
        logger.error(f"Forward error: {e}")

    # Save to DB
    db.save_scientific_post(
        channel_id=channel_id,
        message_id=message.message_id,
        message_text=message_text,
        media_type=media_type,
        categories=categories,
        keywords=keywords,
        hashtags=hashtags,
        forwarded_to=destination,
        forwarded_msg_id=forwarded_msg_id,
        post_date=now,
    )

    # ── Send to external platforms ──
    platforms = db.get_all_platforms()
    if platforms and message_text:
        payload = {
            "source_channel": channel_name,
            "channel_link": channel_link,
            "content": message_text[:2000],
            "media_type": media_type,
            "categories": categories,
            "keywords": keywords[:10],
            "hashtags": hashtags,
            "date": date_str,
            "time": time_str,
            "score": score,
        }
        for platform in platforms:
            await send_to_platform(platform, payload)


async def send_to_platform(platform: dict, payload: dict):
    """Send scientific post to an external platform via webhook."""
    try:
        headers = {"Content-Type": "application/json"}
        if platform.get("api_key"):
            headers["Authorization"] = f"Bearer {platform['api_key']}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                platform["webhook_url"],
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status in (200, 201, 204):
                    db.increment_platform_posts(platform["id"])
                    logger.info(f"Sent to platform {platform['name']} — status {resp.status}")
                else:
                    logger.warning(f"Platform {platform['name']} returned {resp.status}")
    except Exception as e:
        logger.error(f"Platform {platform['name']} error: {e}")
