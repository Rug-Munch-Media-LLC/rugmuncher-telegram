"""
Rug Muncher — Scheduled Jobs
============================
Background tasks:
  • Daily digest (00:00 UTC) — Community scan rankings
  • Hourly trend check — Spot viral tokens
  • Cleanup — Prune old data
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from bot.database import get_db, ScanDB, UserDB
from bot.channels import ChannelManager, CHANNELS, format_alert_card

logger = logging.getLogger("scheduler")


class DailyDigest:
    """Generate and post daily community scan summaries."""

    @staticmethod
    def get_yesterday_stats() -> Dict:
        with get_db() as db:
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

            total_scans = db.execute(
                "SELECT COUNT(*) FROM scans WHERE DATE(created_at) = ?", (yesterday,)
            ).fetchone()[0]

            top_risky = db.execute("""
                SELECT address, chain, risk_score, risk_level, COUNT(*) as scan_count
                FROM scans
                WHERE DATE(created_at) = ? AND risk_score >= 70
                GROUP BY address
                ORDER BY scan_count DESC, risk_score DESC
                LIMIT 5
            """, (yesterday,)).fetchall()

            top_safe = db.execute("""
                SELECT address, chain, risk_score, risk_level, COUNT(*) as scan_count
                FROM scans
                WHERE DATE(created_at) = ? AND risk_score <= 25
                GROUP BY address
                ORDER BY scan_count DESC, risk_score ASC
                LIMIT 5
            """, (yesterday,)).fetchall()

            active_users = db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM scans WHERE DATE(created_at) = ?", (yesterday,)
            ).fetchone()[0]

            return {
                "date": yesterday,
                "total_scans": total_scans,
                "active_users": active_users,
                "top_risky": [dict(r) for r in top_risky],
                "top_safe": [dict(r) for r in top_safe],
            }

    @staticmethod
    def format_digest(stats: Dict) -> str:
        lines = [
            f"<b>🏘️ COMMUNITY SCAN DIGEST</b>",
            f"<b>╔══════════════════════════════════════╗</b>",
            f"<b>║  📊 {stats['date']} Summary</b>",
            f"<b>╚══════════════════════════════════════╝</b>",
            f"",
            f"<b>📈 Activity:</b>",
            f"  Total scans: <b>{stats['total_scans']}</b>",
            f"  Active hunters: <b>{stats['active_users']}</b>",
            f"",
        ]

        if stats["top_risky"]:
            lines.append(f"<b>🚨 Most Warned (High Risk):</b>")
            for i, t in enumerate(stats["top_risky"], 1):
                short = f"{t['address'][:6]}...{t['address'][-4:]}"
                lines.append(f"  {i}. <code>{short}</code> — {t['risk_score']}/100 ({t['scan_count']} scans)")
            lines.append("")

        if stats["top_safe"]:
            lines.append(f"<b>💎 Most Scanned Gems (Low Risk):</b>")
            for i, t in enumerate(stats["top_safe"], 1):
                short = f"{t['address'][:6]}...{t['address'][-4:]}"
                lines.append(f"  {i}. <code>{short}</code> — {t['risk_score']}/100 ({t['scan_count']} scans)")
            lines.append("")

        lines.append(f"<i>Scan with @rugmuncherbot for full dossiers</i>")
        lines.append(f"<i>Join the hunt — /invite your friends</i>")

        return "\n".join(lines)


class Scheduler:
    """Simple async scheduler for background tasks."""

    def __init__(self, channel_manager: ChannelManager):
        self.channel_manager = channel_manager
        self.running = False

    async def run(self):
        self.running = True
        logger.info("⏰ Scheduler started")

        while self.running:
            now = datetime.utcnow()
            # Run daily digest at 00:05 UTC
            if now.hour == 0 and now.minute < 5:
                await self._daily_digest()
                await asyncio.sleep(3600)  # Sleep past the hour
            else:
                await asyncio.sleep(60)

    async def _daily_digest(self):
        if not self.channel_manager.is_configured("community_scans"):
            return
        try:
            stats = DailyDigest.get_yesterday_stats()
            text = DailyDigest.format_digest(stats)
            await self.channel_manager.post("community_scans", text)
            logger.info(f"📊 Daily digest posted ({stats['total_scans']} scans)")
        except Exception as e:
            logger.error(f"Daily digest failed: {e}")

    def stop(self):
        self.running = False
