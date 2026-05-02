"""
Rug Muncher — SocialFi Engine
=============================
Social finance layer:
  • Referral system with point rewards
  • Social points economy
  • Leaderboards (global, weekly, monthly)
  • Community challenges
  • Share-to-earn mechanics
  • Social ranks & titles
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from bot.database import (
    UserDB, SocialPointsDB, ReferralDB, ChallengeDB, ShareDB, DailyUsageDB
)


# ── Social Ranks ──
SOCIAL_RANKS = [
    (0,     "🌱 Seed",        "Just planted"),
    (500,   "🌿 Sprout",      "Growing roots"),
    (1500,  "🪴 Bush",        "Getting noticed"),
    (3000,  "🌳 Tree",        "Community pillar"),
    (6000,  "🔥 Influencer",  "Moves markets"),
    (12000, "🌟 KOL",         "Key opinion leader"),
    (25000, "👑 DeFi King",   "Legendary status"),
    (50000, "🐋 Whale",       "Untouchable"),
]


def get_social_rank(points: int) -> Tuple[str, str]:
    """Get rank emoji+name and description for a point total."""
    current = SOCIAL_RANKS[0]
    for threshold, rank_name, desc in SOCIAL_RANKS:
        if points >= threshold:
            current = (threshold, rank_name, desc)
        else:
            break
    return current[1], current[2]


def get_next_rank(points: int) -> Optional[Tuple[str, int]]:
    """Returns (next_rank_name, points_needed) or None if max rank."""
    for threshold, rank_name, _ in SOCIAL_RANKS:
        if points < threshold:
            return rank_name, threshold - points
    return None


# ── Referral Engine ──

class ReferralEngine:
    """Generate and track referral links."""

    @staticmethod
    def get_link(bot_username: str, user_id: str) -> str:
        """Generate Telegram referral link."""
        payload = hashlib.sha256(f"rm_ref_{user_id}".encode()).hexdigest()[:8]
        return f"https://t.me/{bot_username}?start=ref_{user_id}"

    @staticmethod
    def parse_start_param(param: str) -> Optional[str]:
        """Parse referrer ID from /start parameter."""
        if param and param.startswith("ref_"):
            return param.replace("ref_", "")
        return None

    @staticmethod
    def register_referral(referrer_id: str, referred_id: str) -> bool:
        """Register a new referral relationship."""
        if referrer_id == referred_id:
            return False
        return ReferralDB.create_referral(referrer_id, referred_id)


# ── Leaderboard Engine ──

class LeaderboardEngine:
    """Generate leaderboards with caching logic."""

    @staticmethod
    def get_global(limit: int = 20) -> List[Dict]:
        rows = SocialPointsDB.get_leaderboard(limit)
        results = []
        for i, row in enumerate(rows, 1):
            rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            name = row.get('first_name') or row.get('username') or f"Hunter{row['user_id'][:4]}"
            rank_name, _ = get_social_rank(row['total_points'])
            results.append({
                "position": i,
                "rank_emoji": rank_emoji,
                "name": name,
                "user_id": row['user_id'],
                "points": row['total_points'],
                "social_rank": rank_name,
                "referral_points": row['referral_points'],
                "scan_points": row['scan_points'],
                "share_points": row['share_points'],
                "challenge_points": row['challenge_points'],
            })
        return results

    @staticmethod
    def get_user_rank(user_id: str) -> int:
        """Get user's global rank."""
        rows = SocialPointsDB.get_leaderboard(limit=10000)
        for i, row in enumerate(rows, 1):
            if row['user_id'] == user_id:
                return i
        return 0


# ── Challenge Engine ──

class ChallengeEngine:
    """Manage community challenges."""

    @staticmethod
    def get_available(user_id: str) -> List[Dict]:
        """Get active challenges not yet completed by user."""
        active = ChallengeDB.get_active()
        completed = {c['challenge_key'] for c in ChallengeDB.get_user_completed(user_id)}
        return [c for c in active if c['key'] not in completed]

    @staticmethod
    def check_daily_grind(user_id: str) -> bool:
        """Check if user scanned 5+ contracts today."""
        usage = DailyUsageDB.get_usage(user_id)
        return usage.get("contract", 0) >= 5

    @staticmethod
    def check_first_scan(user_id: str) -> bool:
        """Check if user has done at least one scan."""
        user = UserDB.get_user(user_id)
        return user is not None and user.get('scans_total', 0) > 0

    @staticmethod
    def auto_check(user_id: str, scan_result: Optional[Dict] = None) -> List[Dict]:
        """Auto-check and complete challenges. Returns newly completed."""
        completed = []

        # first_scan
        if ChallengeEngine.check_first_scan(user_id):
            pts = ChallengeDB.complete_challenge(user_id, "first_scan")
            if pts:
                completed.append({"key": "first_scan", "name": "First Blood", "points": pts})

        # daily_grind
        if ChallengeEngine.check_daily_grind(user_id):
            pts = ChallengeDB.complete_challenge(user_id, "daily_grind")
            if pts:
                completed.append({"key": "daily_grind", "name": "Daily Grind", "points": pts})

        # rug_spotter
        if scan_result and scan_result.get('risk_score', 0) >= 81:
            pts = ChallengeDB.complete_challenge(user_id, "rug_spotter")
            if pts:
                completed.append({"key": "rug_spotter", "name": "Rug Spotter", "points": pts})

        return completed


# ── Share Engine ──

class ShareEngine:
    """Share-to-earn mechanics."""

    PLATFORMS = {
        "telegram": "📨 Telegram",
        "twitter": "🐦 X / Twitter",
        "discord": "💬 Discord",
    }

    @staticmethod
    def share_scan(user_id: str, address: str, platform: str) -> Tuple[int, str]:
        """Record a share and return (points_earned, message)."""
        if platform not in ShareEngine.PLATFORMS:
            return 0, "Unknown platform"
        points = ShareDB.record_share(user_id, address, platform)
        if points == 0:
            return 0, "Daily share limit reached for this platform (max 10/day)"
        return points, f"Earned {points} points for sharing to {ShareEngine.PLATFORMS[platform]}!"


# ── SocialFi Profile Builder ──

def build_social_profile(user_id: str, bot_username: str) -> Dict:
    """Build complete SocialFi profile for a user."""
    points = SocialPointsDB.get_points(user_id)
    referrals = ReferralDB.get_referrals(user_id)
    rank_name, rank_desc = get_social_rank(points['total_points'])
    next_rank = get_next_rank(points['total_points'])
    global_rank = LeaderboardEngine.get_user_rank(user_id)
    completed = ChallengeDB.get_user_completed(user_id)
    available = ChallengeEngine.get_available(user_id)

    return {
        "points": points,
        "rank_name": rank_name,
        "rank_desc": rank_desc,
        "next_rank": next_rank,
        "global_rank": global_rank,
        "referrals": referrals,
        "completed_challenges": completed,
        "available_challenges": available,
        "referral_link": ReferralEngine.get_link(bot_username, user_id),
    }


# ── Singletons ──
referral_engine = ReferralEngine()
leaderboard_engine = LeaderboardEngine()
challenge_engine = ChallengeEngine()
share_engine = ShareEngine()
