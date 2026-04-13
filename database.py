"""
Database Manager
================
Handles all SQLite operations for the Science Bot.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize all database tables."""
    with get_connection() as conn:
        conn.executescript("""
            -- Bot global settings
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            -- Channels the bot monitors (added as admin)
            CREATE TABLE IF NOT EXISTS monitored_channels (
                channel_id      TEXT PRIMARY KEY,
                channel_name    TEXT,
                channel_link    TEXT,
                added_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active       INTEGER DEFAULT 1,
                total_posts     INTEGER DEFAULT 0,
                scientific_posts INTEGER DEFAULT 0,
                total_videos    INTEGER DEFAULT 0,
                total_images    INTEGER DEFAULT 0,
                total_docs      INTEGER DEFAULT 0
            );

            -- Every scientific post detected
            CREATE TABLE IF NOT EXISTS scientific_posts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id      TEXT,
                message_id      INTEGER,
                message_text    TEXT,
                media_type      TEXT,
                categories      TEXT,
                detected_keywords TEXT,
                detected_hashtags TEXT,
                forwarded_to    TEXT,
                forwarded_msg_id INTEGER,
                post_date       TIMESTAMP,
                recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(channel_id) REFERENCES monitored_channels(channel_id)
            );

            -- External platforms (webhooks)
            CREATE TABLE IF NOT EXISTS external_platforms (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE,
                webhook_url TEXT,
                api_key     TEXT,
                platform_type TEXT DEFAULT 'webhook',
                is_active   INTEGER DEFAULT 1,
                posts_sent  INTEGER DEFAULT 0,
                added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Classification keywords customization
            CREATE TABLE IF NOT EXISTS custom_keywords (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword  TEXT UNIQUE,
                language TEXT DEFAULT 'ar',
                weight   INTEGER DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Bot admin users
            CREATE TABLE IF NOT EXISTS bot_admins (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Database initialized successfully.")


# ─────────────────────────────────────────────────
#   Settings
# ─────────────────────────────────────────────────
def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, value)
        )


# ─────────────────────────────────────────────────
#   Monitored Channels
# ─────────────────────────────────────────────────
def add_channel(channel_id: str, channel_name: str, channel_link: str = ""):
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO monitored_channels
               (channel_id, channel_name, channel_link)
               VALUES(?, ?, ?)""",
            (channel_id, channel_name, channel_link),
        )


def remove_channel(channel_id: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE monitored_channels SET is_active=0 WHERE channel_id=?",
            (channel_id,),
        )


def get_channel(channel_id: str) -> Optional[Dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM monitored_channels WHERE channel_id=?", (channel_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_channels(active_only: bool = True) -> List[Dict]:
    with get_connection() as conn:
        query = "SELECT * FROM monitored_channels"
        if active_only:
            query += " WHERE is_active=1"
        query += " ORDER BY added_at DESC"
        return [dict(r) for r in conn.execute(query).fetchall()]


def update_channel_info(channel_id: str, channel_name: str, channel_link: str):
    with get_connection() as conn:
        conn.execute(
            """UPDATE monitored_channels
               SET channel_name=?, channel_link=?
               WHERE channel_id=?""",
            (channel_name, channel_link, channel_id),
        )


def increment_channel_stats(
    channel_id: str,
    is_scientific: bool = False,
    media_type: str = "text"
):
    with get_connection() as conn:
        conn.execute(
            "UPDATE monitored_channels SET total_posts=total_posts+1 WHERE channel_id=?",
            (channel_id,),
        )
        if is_scientific:
            conn.execute(
                "UPDATE monitored_channels SET scientific_posts=scientific_posts+1 WHERE channel_id=?",
                (channel_id,),
            )
        if media_type == "video":
            conn.execute(
                "UPDATE monitored_channels SET total_videos=total_videos+1 WHERE channel_id=?",
                (channel_id,),
            )
        elif media_type == "photo":
            conn.execute(
                "UPDATE monitored_channels SET total_images=total_images+1 WHERE channel_id=?",
                (channel_id,),
            )
        elif media_type in ("document", "audio"):
            conn.execute(
                "UPDATE monitored_channels SET total_docs=total_docs+1 WHERE channel_id=?",
                (channel_id,),
            )


# ─────────────────────────────────────────────────
#   Scientific Posts
# ─────────────────────────────────────────────────
def save_scientific_post(
    channel_id: str,
    message_id: int,
    message_text: str,
    media_type: str,
    categories: List[str],
    keywords: List[str],
    hashtags: List[str],
    forwarded_to: str,
    forwarded_msg_id: Optional[int],
    post_date: datetime,
):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO scientific_posts
               (channel_id, message_id, message_text, media_type, categories,
                detected_keywords, detected_hashtags, forwarded_to, forwarded_msg_id, post_date)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                channel_id,
                message_id,
                message_text[:1000],
                media_type,
                ",".join(categories),
                ",".join(keywords[:20]),
                ",".join(hashtags[:20]),
                forwarded_to,
                forwarded_msg_id,
                post_date.isoformat(),
            ),
        )


def get_recent_scientific_posts(limit: int = 10) -> List[Dict]:
    with get_connection() as conn:
        return [
            dict(r)
            for r in conn.execute(
                """SELECT sp.*, mc.channel_name
                   FROM scientific_posts sp
                   LEFT JOIN monitored_channels mc ON sp.channel_id=mc.channel_id
                   ORDER BY sp.recorded_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        ]


# ─────────────────────────────────────────────────
#   Global Statistics
# ─────────────────────────────────────────────────
def get_global_stats() -> Dict:
    with get_connection() as conn:
        totals = conn.execute(
            """SELECT
                COUNT(*) as total_channels,
                SUM(total_posts) as total_posts,
                SUM(scientific_posts) as scientific_posts,
                SUM(total_videos) as total_videos,
                SUM(total_images) as total_images,
                SUM(total_docs) as total_docs
               FROM monitored_channels WHERE is_active=1"""
        ).fetchone()

        platforms = conn.execute(
            "SELECT COUNT(*) as cnt, SUM(posts_sent) as sent FROM external_platforms WHERE is_active=1"
        ).fetchone()

        today_count = conn.execute(
            """SELECT COUNT(*) as cnt FROM scientific_posts
               WHERE DATE(recorded_at)=DATE('now')"""
        ).fetchone()

        return {
            "total_channels": totals["total_channels"] or 0,
            "total_posts": totals["total_posts"] or 0,
            "scientific_posts": totals["scientific_posts"] or 0,
            "total_videos": totals["total_videos"] or 0,
            "total_images": totals["total_images"] or 0,
            "total_docs": totals["total_docs"] or 0,
            "platforms_count": platforms["cnt"] or 0,
            "platforms_sent": platforms["sent"] or 0,
            "today_count": today_count["cnt"] or 0,
        }


# ─────────────────────────────────────────────────
#   External Platforms
# ─────────────────────────────────────────────────
def add_platform(name: str, webhook_url: str, api_key: str = "", platform_type: str = "webhook"):
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO external_platforms
               (name, webhook_url, api_key, platform_type)
               VALUES(?,?,?,?)""",
            (name, webhook_url, api_key, platform_type),
        )


def remove_platform(name: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE external_platforms SET is_active=0 WHERE name=?", (name,)
        )


def get_all_platforms(active_only: bool = True) -> List[Dict]:
    with get_connection() as conn:
        query = "SELECT * FROM external_platforms"
        if active_only:
            query += " WHERE is_active=1"
        return [dict(r) for r in conn.execute(query).fetchall()]


def increment_platform_posts(platform_id: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE external_platforms SET posts_sent=posts_sent+1 WHERE id=?",
            (platform_id,),
        )


# ─────────────────────────────────────────────────
#   Custom Keywords
# ─────────────────────────────────────────────────
def add_custom_keyword(keyword: str, language: str = "ar", weight: int = 1):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO custom_keywords(keyword,language,weight) VALUES(?,?,?)",
            (keyword.lower(), language, weight),
        )


def remove_custom_keyword(keyword: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM custom_keywords WHERE keyword=?", (keyword.lower(),))


def get_custom_keywords() -> List[Dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM custom_keywords").fetchall()]


# ─────────────────────────────────────────────────
#   Bot Admins
# ─────────────────────────────────────────────────
def add_bot_admin(user_id: int, username: str = ""):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO bot_admins(user_id, username) VALUES(?,?)",
            (user_id, username),
        )


def remove_bot_admin(user_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM bot_admins WHERE user_id=?", (user_id,))


def get_bot_admins() -> List[int]:
    with get_connection() as conn:
        return [r["user_id"] for r in conn.execute("SELECT user_id FROM bot_admins").fetchall()]
