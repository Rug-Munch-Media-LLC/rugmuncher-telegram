"""
Rug Muncher — Gamification Engine
==================================
Rarity cards, achievements, streaks, collections, teaser system.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

from config import DATA_DIR

try:
    from bot.database import UserDB, ScanDB, CollectionDB, AchievementDB
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# ── Rarity System ──
RARITY_TIERS = {
    "COMMON":    {"min": 0,  "max": 20,  "emoji": "🌿", "color": "#00C853", "title": "COMMON",    "flavor": "Nothing special here."},
    "RARE":      {"min": 21, "max": 40,  "emoji": "💎", "color": "#00B0FF", "title": "RARE",      "flavor": "Worth a closer look."},
    "EPIC":      {"min": 41, "max": 60,  "emoji": "🔮", "color": "#AA00FF", "title": "EPIC",      "flavor": "Danger signals detected."},
    "LEGENDARY": {"min": 61, "max": 80,  "emoji": "🔥", "color": "#FF6D00", "title": "LEGENDARY", "flavor": "High probability rug!"},
    "MYTHIC":    {"min": 81, "max": 100, "emoji": "💀", "color": "#FF1744", "title": "MYTHIC",    "flavor": "RUN. THIS IS A HONEYPOT."},
}

# ── Achievement System ──
ACHIEVEMENTS = {
    "first_blood":       {"name": "First Blood",       "emoji": "🩸", "desc": "Perform your first scan"},
    "rug_hunter":        {"name": "Rug Hunter",        "emoji": "🏴‍☠️", "desc": "Detect a MYTHIC risk token"},
    "legendary_spotter": {"name": "Legendary Spotter", "emoji": "🔥", "desc": "Detect a LEGENDARY risk token"},
    "safe_hands":        {"name": "Safe Hands",        "emoji": "🤲", "desc": "Scan 5 SAFE tokens in a row"},
    "diamond_hands":     {"name": "Diamond Hands",     "emoji": "💎", "desc": "Scan 50 tokens total"},
    "whale_watcher":     {"name": "Whale Watcher",     "emoji": "🐋", "desc": "Scan a known whale wallet"},
    "night_owl":         {"name": "Night Owl",         "emoji": "🦉", "desc": "Scan at 3 AM"},
    "bounty_hunter":     {"name": "Bounty Hunter",     "emoji": "🎯", "desc": "Find 10 high-risk tokens"},
    "collector":         {"name": "Collector",         "emoji": "📚", "desc": "Collect 25 unique risk cards"},
    "maximalist":        {"name": "Maximalist",        "emoji": "👑", "desc": "Own 100 unique risk cards"},
}

# ── Finding Categories (for teaser system) ──
FINDING_CATEGORIES = {
    "security":   {"emoji": "🛡️", "name": "Security Issues",     "icon": "🔒"},
    "liquidity":  {"emoji": "💧", "name": "Liquidity Warnings",  "icon": "⚠️"},
    "holders":    {"emoji": "👥", "name": "Holder Red Flags",    "icon": "🚩"},
    "social":     {"emoji": "📰", "name": "Social Intel",        "icon": "📡"},
    "deployer":   {"emoji": "👤", "name": "Deployer History",    "icon": "🕵️"},
    "novel":      {"emoji": "🤖", "name": "AI Detection",        "icon": "🧠"},
}


def get_rarity(risk_score: int) -> Dict:
    """Get rarity tier for a risk score."""
    for tier, data in RARITY_TIERS.items():
        if data["min"] <= risk_score <= data["max"]:
            return {"tier": tier, **data}
    return {"tier": "COMMON", **RARITY_TIERS["COMMON"]}


def categorize_findings(findings: List[str]) -> Dict[str, List[str]]:
    """Group findings into categories for the teaser system."""
    categories = {k: [] for k in FINDING_CATEGORIES}
    categories["other"] = []

    for finding in findings:
        f_lower = finding.lower()
        categorized = False
        if any(kw in f_lower for kw in ["mint", "freeze", "mutable", "verified", "security", "honeypot", "exploit", "hack", "contract"]):
            categories["security"].append(finding)
            categorized = True
        elif any(kw in f_lower for kw in ["liquidity", "lp", "pool", "volume", "mc", "market cap"]):
            categories["liquidity"].append(finding)
            categorized = True
        elif any(kw in f_lower for kw in ["holder", "top 10", "supply", "concentration", "gini", "sybil"]):
            categories["holders"].append(finding)
            categorized = True
        elif any(kw in f_lower for kw in ["news", "sentiment", "twitter", "social", "media", "cryptopanic"]):
            categories["social"].append(finding)
            categorized = True
        elif any(kw in f_lower for kw in ["deployer", "creator", "dev", "deployed", "age", "blocktime"]):
            categories["deployer"].append(finding)
            categorized = True
        elif any(kw in f_lower for kw in ["replica", "clone", "ai scan", "novel", "anomaly", "cluster", "velocity", "manipulation"]):
            categories["novel"].append(finding)
            categorized = True

        if not categorized:
            categories["other"].append(finding)

    return {k: v for k, v in categories.items() if v}


def build_teaser_message(
    address: str,
    risk_score: int,
    risk_level: str,
    findings: List[str],
    chain: str,
    tier: str = "free",
    breakdown: dict = None,
) -> str:
    """
    Build a gamified, mysterious message for free scans.
    Shows category counts with LOCKED indicators instead of raw findings.
    Includes 100-point forensic breakdown when available.
    """
    rarity = get_rarity(risk_score)
    categories = categorize_findings(findings)
    total_hidden = len(findings)
    breakdown = breakdown or {}

    # Card ID (deterministic based on address)
    card_id = f"#{hashlib.sha256(address.encode()).hexdigest()[:6].upper()}"

    lines = [
        f"<b>╔══════════════════════════════════════╗</b>",
        f"<b>║  🎴 RUG MUNCHER RISK CARD          ║</b>",
        f"<b>╚══════════════════════════════════════╝</b>",
        f"",
        f"<b>{rarity['emoji']} {rarity['title']} RISK CARD</b>  <code>{card_id}</code>",
        f"<i>\"{rarity['flavor']}\"</i>",
        f"",
        f"<b>📍 Target:</b> <code>{address[:12]}...{address[-6:]}</code>",
        f"<b>⛓ Chain:</b> {chain.upper()}",
        f"",
        f"<b>💀 Danger Level:</b> {risk_score}/100",
        f"<b>📊 Classification:</b> {risk_level}",
        f"",
    ]

    # 100-point forensic breakdown
    if breakdown:
        lines.append(f"<b>🛡️ Forensic Breakdown (100 pts):</b>")
        cat_emojis = {
            "Contract Security": "🔒",
            "Liquidity Health": "💧",
            "Holder Distribution": "👥",
            "Creator / Dev Profile": "🎭",
            "Market Behavior": "📈",
        }
        for cat, score in breakdown.items():
            emoji = cat_emojis.get(cat, "📊")
            bar = _score_bar(score)
            lines.append(f"  {emoji} <b>{cat}:</b> {score} pts  <code>{bar}</code>")
        lines.append("")

    # Gamified finding categories with LOCKED indicators
    if categories:
        lines.append(f"<b>🎒 Loot Discovered:</b>")
        for cat_key, cat_findings in categories.items():
            cat_info = FINDING_CATEGORIES.get(cat_key, {"emoji": "📦", "name": "Unknown", "icon": "❓"})
            count = len(cat_findings)
            if tier == "free":
                lines.append(f"  {cat_info['emoji']} <b>{cat_info['name']}</b> — {cat_info['icon']} <code>{count} SECRETS LOCKED</code>")
            else:
                lines.append(f"  {cat_info['emoji']} <b>{cat_info['name']}</b> ({count})")
                for f in cat_findings[:3]:
                    lines.append(f"     └─ {f}")

        if tier == "free" and total_hidden > 0:
            lines.append(f"")
            lines.append(f"<b>🔐 {total_hidden} classified intel items hidden</b>")
            lines.append(f"<i>Upgrade to decrypt full dossier...</i>")
    else:
        lines.append(f"<b>✨ No threats detected in surface scan</b>")

    lines.extend([
        f"",
        f"<b>🏆 Card Value:</b> {rarity['emoji']} {rarity['title']}",
    ])

    if tier == "free":
        lines.append(f"")
        lines.append(f"<i>💡 Collect this card or scan another address...</i>")

    return "\n".join(lines)


def _score_bar(score: int, width: int = 10) -> str:
    """Mini ASCII progress bar for category score."""
    filled = min(width, max(0, int(score / 5)))
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return bar


def build_premium_unlock_message(scan_type: str = "contract") -> str:
    """Build the premium unlock message with gamified copy."""
    price = 2.0 if scan_type == "contract" else 5.0
    return (
        f"<b>🔓 DECRYPT CLASSIFIED INTEL?</b>\n\n"
        f"This card contains hidden data:\n"
        f"  🔓 Full security audit\n"
        f"  🔓 Deployer background check\n"
        f"  🔓 Honeypot simulation results\n"
        f"  🔓 AI vulnerability report\n"
        f"  🔓 Social sentiment analysis\n"
        f"  🔓 PDF collector's edition card\n\n"
        f"<b>💰 Unlock Cost: ${price:.0f}</b>\n"
        f"<i>Or go unlimited with Pro membership...</i>"
    )


# ── Achievement Engine ──

class AchievementEngine:
    """Track user achievements, streaks, and collections."""

    def __init__(self):
        self.data_file = DATA_DIR / "gamification.json"
        self.data = self._load()

    def _load(self) -> Dict:
        if self.data_file.exists():
            return json.loads(self.data_file.read_text())
        return {}

    def _save(self):
        self.data_file.write_text(json.dumps(self.data, indent=2))

    def _get_user(self, user_id: str) -> Dict:
        if user_id not in self.data:
            self.data[user_id] = {
                "scans": 0,
                "achievements": [],
                "collection": [],
                "streak_safe": 0,
                "streak_total": 0,
                "high_risk_count": 0,
                "last_scan_time": None,
                "first_scan": None,
            }
        return self.data[user_id]

    def record_scan(self, user_id: str, address: str, risk_score: int, risk_level: str, scan_type: str = "contract") -> List[Dict]:
        """Record a scan and return any newly unlocked achievements."""
        user = self._get_user(user_id)
        now = datetime.utcnow().isoformat()
        new_achievements = []

        # Basic stats
        user["scans"] += 1
        user["streak_total"] += 1
        if not user["first_scan"]:
            user["first_scan"] = now

        # Streak tracking
        if risk_level == "SAFE":
            user["streak_safe"] += 1
        else:
            user["streak_safe"] = 0

        if risk_score >= 60:
            user["high_risk_count"] += 1

        # Collection (deduplicated by address)
        card_hash = hashlib.sha256(address.encode()).hexdigest()[:8]
        if card_hash not in user["collection"]:
            user["collection"].append(card_hash)

        user["last_scan_time"] = now

        # Check achievements
        unlocked = set(user["achievements"])

        if user["scans"] == 1 and "first_blood" not in unlocked:
            user["achievements"].append("first_blood")
            new_achievements.append(ACHIEVEMENTS["first_blood"])

        if risk_score >= 81 and "rug_hunter" not in unlocked:
            user["achievements"].append("rug_hunter")
            new_achievements.append(ACHIEVEMENTS["rug_hunter"])

        if 61 <= risk_score <= 80 and "legendary_spotter" not in unlocked:
            user["achievements"].append("legendary_spotter")
            new_achievements.append(ACHIEVEMENTS["legendary_spotter"])

        if user["streak_safe"] >= 5 and "safe_hands" not in unlocked:
            user["achievements"].append("safe_hands")
            new_achievements.append(ACHIEVEMENTS["safe_hands"])

        if user["scans"] >= 50 and "diamond_hands" not in unlocked:
            user["achievements"].append("diamond_hands")
            new_achievements.append(ACHIEVEMENTS["diamond_hands"])

        if user["high_risk_count"] >= 10 and "bounty_hunter" not in unlocked:
            user["achievements"].append("bounty_hunter")
            new_achievements.append(ACHIEVEMENTS["bounty_hunter"])

        if len(user["collection"]) >= 25 and "collector" not in unlocked:
            user["achievements"].append("collector")
            new_achievements.append(ACHIEVEMENTS["collector"])

        if len(user["collection"]) >= 100 and "maximalist" not in unlocked:
            user["achievements"].append("maximalist")
            new_achievements.append(ACHIEVEMENTS["maximalist"])

        # Night owl (3 AM UTC)
        current_hour = datetime.utcnow().hour
        if current_hour == 3 and "night_owl" not in unlocked:
            user["achievements"].append("night_owl")
            new_achievements.append(ACHIEVEMENTS["night_owl"])

        self._save()

        # Sync to SQLite if available
        if DB_AVAILABLE:
            try:
                rarity = get_rarity(risk_score)
                UserDB.ensure_user(user_id)
                ScanDB.record_scan(user_id, address, "unknown", scan_type, risk_score, risk_level, rarity["tier"], [])
                CollectionDB.add_or_update(user_id, address, "unknown", rarity["tier"])
                for ach in new_achievements:
                    key = [k for k, v in ACHIEVEMENTS.items() if v["name"] == ach["name"]]
                    if key:
                        AchievementDB.unlock(user_id, key[0])
            except Exception:
                pass

        return new_achievements

    def get_profile(self, user_id: str) -> Dict:
        """Get full user gamification profile."""
        user = self._get_user(user_id)
        unlocked = [ACHIEVEMENTS[a] for a in user["achievements"] if a in ACHIEVEMENTS]
        total = len(ACHIEVEMENTS)

        return {
            "scans": user["scans"],
            "collection_size": len(user["collection"]),
            "safe_streak": user["streak_safe"],
            "achievements_unlocked": len(unlocked),
            "achievements_total": total,
            "achievement_list": unlocked,
            "progress_pct": round(len(unlocked) / total * 100, 1),
            "rank": self._get_rank(user),
        }

    def _get_rank(self, user: Dict) -> str:
        """Determine user rank based on achievements and scans."""
        ach_count = len(user["achievements"])
        scans = user["scans"]
        if ach_count >= 8 or scans >= 200:
            return "🏆 GRANDMASTER"
        elif ach_count >= 5 or scans >= 100:
            return "💎 DIAMOND"
        elif ach_count >= 3 or scans >= 50:
            return "🥇 GOLD"
        elif ach_count >= 1 or scans >= 10:
            return "🥈 SILVER"
        return "🥉 BRONZE"


# Singleton
achievement_engine = AchievementEngine()
