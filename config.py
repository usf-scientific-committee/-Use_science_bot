"""
Bot Configuration
================
Scientific Channel Monitor Bot - Configuration File
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────
#   Bot Core Settings
# ─────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── المالك الأساسي (صلاحيات كاملة لا تُسحب) ──
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ── المشرفون الإضافيون ──
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# ─────────────────────────────────────────────────
#   مستويات الصلاحيات
# ─────────────────────────────────────────────────
# OWNER  → صلاحيات كاملة بما فيها حذف المشرفين وإيقاف البوت
# ADMIN  → إدارة القنوات والإعدادات
# USER   → عرض فقط (لا صلاحيات)

# ─────────────────────────────────────────────────
#   Channel & Database
# ─────────────────────────────────────────────────
DESTINATION_CHANNEL = os.getenv("DESTINATION_CHANNEL", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/science_bot.db")

# ─────────────────────────────────────────────────
#   Classification Sensitivity
# ─────────────────────────────────────────────────
# 1 = Low (few keywords enough), 5 = High (strict)
CLASSIFICATION_THRESHOLD = int(os.getenv("CLASSIFICATION_THRESHOLD", "2"))

# ─────────────────────────────────────────────────
#   Message Templates (Arabic UI)
# ─────────────────────────────────────────────────
FORWARD_TEMPLATE = """
🔬 *محتوى علمي جديد*
━━━━━━━━━━━━━━━━━━━━
📢 *المصدر:* {channel_name}
🔗 *رابط القناة:* {channel_link}
📅 *التاريخ:* {date}
🕐 *الوقت:* {time}
🏷️ *التصنيف:* {categories}
━━━━━━━━━━━━━━━━━━━━
"""

BOT_VERSION = "2.1.0"
