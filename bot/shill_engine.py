"""
Rug Muncher — Auto-Shill Engine
================================
Cross-promotes Rug Muncher Bot, Muncher Maps, and RMI
in all free intelligence channels.

Rules:
  • Shills only in FREE channels
  • Max 1 shill per channel per 6 hours
  • Rotates between different promo messages
  • Never shills in paid/Alpha channels
"""

import random
from typing import List, Dict
from datetime import datetime, timedelta


SHILL_MESSAGES = [
    {
        "title": "🛡️ Stay Safe Out There",
        "body": (
            "<b>🛡️ Don't get rekt. Scan first.</b>\n\n"
            "Get full forensic scans, risk cards, and alpha intel:\n"
            "  👉 <b>@rugmuncherbot</b>\n\n"
            "Every scan reveals a collectible Risk Card."
        ),
    },
    {
        "title": "🗺️ Muncher Maps",
        "body": (
            "<b>🗺️ Explore the Muncher Maps</b>\n\n"
            "Visual bubble maps, holder distributions, and on-chain forensics.\n"
            "  👉 <b>munchermaps.ai</b>\n\n"
            "See what the bots can't show you."
        ),
    },
    {
        "title": "🧠 Rug Munch Intelligence",
        "body": (
            "<b>🧠 Rug Munch Intelligence (RMI)</b>\n\n"
            "Deep-dive threat intel, serial rugger tracking, and exploit forensics.\n"
            "  👉 <b>@RugMunchIntel</b>\n\n"
            "Knowledge is your best armor."
        ),
    },
    {
        "title": "💬 Join the Community",
        "body": (
            "<b>💬 Join the Rug Muncher Community</b>\n\n"
            "Alpha leaks, scan requests, and degen chat.\n"
            "  👉 <b>@RugMuncherChat</b>\n\n"
            "Don't ape alone."
        ),
    },
    {
        "title": "🎮 Gamified Scanning",
        "body": (
            "<b>🎮 Collect Risk Cards</b>\n\n"
            "Every scan unlocks a collectible card with rarity tiers.\n"
            "Build your collection, unlock achievements, rank up!\n"
            "  👉 <b>@rugmuncherbot</b>\n\n"
            "Start your collection today."
        ),
    },
    {
        "title": "🐋 Crypto Alpha",
        "body": (
            "<b>🐋 Want the real alpha?</b>\n\n"
            "Whale movements, insider accumulation, smart money clustering.\n"
            "Upgrade to Crypto Alpha for $5/mo.\n"
            "  👉 <b>@rugmuncherbot → /premium</b>\n\n"
            "Follow the smart money."
        ),
    },
]

FREE_CHANNEL_KEYS = [
    "community_scans",
    "crypto_alerts",
    "safe_gems",
    "dev_watch",
    "honeypot_traps",
    "launch_radar",
    "sentiment_feed",
]


class ShillEngine:
    """Manages cross-promotion in free channels."""

    SHILL_COOLDOWN_HOURS = 6

    def __init__(self):
        self.last_shill: Dict[str, datetime] = {}

    def can_shill(self, channel_key: str) -> bool:
        """Check if enough time has passed since last shill."""
        if channel_key not in FREE_CHANNEL_KEYS:
            return False
        last = self.last_shill.get(channel_key)
        if not last:
            return True
        return datetime.utcnow() - last > timedelta(hours=self.SHILL_COOLDOWN_HOURS)

    def get_shill(self, channel_key: str) -> str:
        """Get a shill message and record the time."""
        msg = random.choice(SHILL_MESSAGES)
        self.last_shill[channel_key] = datetime.utcnow()
        return (
            f"<b>╔══════════════════════════════════════╗</b>\n"
            f"<b>║  {msg['title']}</b>\n"
            f"<b>╚══════════════════════════════════════╝</b>\n\n"
            f"{msg['body']}\n\n"
            f"<i>— Rug Muncher Intelligence Network</i>"
        )

    def maybe_shill(self, channel_key: str) -> str:
        """Returns shill text if allowed, else empty."""
        if self.can_shill(channel_key):
            return self.get_shill(channel_key)
        return ""


# Singleton
shill_engine = ShillEngine()
