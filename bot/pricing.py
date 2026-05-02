"""
Rug Muncher — Tier Enforcement & Usage Tracking (SQLite-backed)
===============================================================
Replaces JSON files with proper SQLite persistence.
"""

import os
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime, timedelta

from config import DATA_DIR, FREE_DAILY_SCANS, FREE_DAILY_WALLET_SCANS

try:
    from bot.database import DailyUsageDB, UserDB
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


class TierEngine:
    """
    Enforces free tier limits and validates premium access.
    Backed by SQLite for production reliability.
    """

    def check_free_scan(self, user_id: str, scan_type: str = "contract") -> Tuple[bool, str, Dict]:
        """
        Check if a user can still do a free scan today.
        Returns: (allowed, reason, usage_info)
        """
        if DB_AVAILABLE:
            UserDB.ensure_user(user_id)
            allowed, info = DailyUsageDB.increment(user_id, scan_type,
                FREE_DAILY_SCANS if scan_type == "contract" else FREE_DAILY_WALLET_SCANS)
            if not allowed:
                return False, f"Free limit reached ({info['limit']}/{info['limit']}). Upgrade for unlimited scans.", info
            return True, "", info

        # Fallback (should never hit if DB is initialized)
        return True, "", {"used": 0, "limit": 999, "remaining": 999, "tier": "free"}

    def get_usage_stats(self, user_id: str) -> Dict:
        """Get current usage stats for a user."""
        if DB_AVAILABLE:
            return DailyUsageDB.get_usage(user_id)
        return {"contract": 0, "wallet": 0}


tier_engine = TierEngine()
