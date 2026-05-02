"""
Rug Muncher — SQLite Persistence Layer
=======================================
Replaces fragile JSON files with proper relational storage.
Tables: users, scans, achievements, payments, admin_logs
"""

import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

from config import DATA_DIR

DB_PATH = DATA_DIR / "rugmuncher.db"


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                tier TEXT DEFAULT 'free',
                scans_total INTEGER DEFAULT 0,
                scans_contract INTEGER DEFAULT 0,
                scans_wallet INTEGER DEFAULT 0,
                safe_streak INTEGER DEFAULT 0,
                collection_size INTEGER DEFAULT 0,
                achievements_count INTEGER DEFAULT 0,
                rank TEXT DEFAULT 'Novice Hunter'
            );

            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                address TEXT,
                chain TEXT,
                scan_type TEXT,
                risk_score INTEGER,
                risk_level TEXT,
                rarity_tier TEXT,
                findings_json TEXT,
                is_premium INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                achievement_key TEXT,
                unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, achievement_key),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                address TEXT,
                chain TEXT,
                rarity_tier TEXT,
                first_scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                scan_count INTEGER DEFAULT 1,
                UNIQUE(user_id, address),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS daily_usage (
                user_id TEXT,
                date TEXT,
                contract_scans INTEGER DEFAULT 0,
                wallet_scans INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date)
            );

            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id TEXT,
                action TEXT,
                target_id TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_scans_user ON scans(user_id);
            CREATE INDEX IF NOT EXISTS idx_scans_address ON scans(address);
            CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at);

            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id TEXT,
                referred_id TEXT,
                status TEXT DEFAULT 'pending',
                points_awarded INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(referrer_id, referred_id),
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS social_points (
                user_id TEXT PRIMARY KEY,
                total_points INTEGER DEFAULT 0,
                referral_points INTEGER DEFAULT 0,
                scan_points INTEGER DEFAULT 0,
                share_points INTEGER DEFAULT 0,
                challenge_points INTEGER DEFAULT 0,
                lifetime_points INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                name TEXT,
                description TEXT,
                points INTEGER DEFAULT 0,
                expires_at TEXT,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS user_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                challenge_key TEXT,
                completed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, challenge_key),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS shared_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                address TEXT,
                platform TEXT,
                points INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class UserDB:
    """User management and stats."""

    @staticmethod
    def ensure_user(user_id: str, username: str = None, first_name: str = None, last_name: str = None):
        with get_db() as db:
            db.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, first_name, last_name))
            db.execute("""
                UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = ?
            """, (user_id,))

    @staticmethod
    def get_user(user_id: str) -> Optional[Dict]:
        with get_db() as db:
            row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all_users(limit: int = 1000, offset: int = 0) -> List[Dict]:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def count_users() -> int:
        with get_db() as db:
            return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    @staticmethod
    def count_active_today() -> int:
        with get_db() as db:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            return db.execute(
                "SELECT COUNT(DISTINCT user_id) FROM scans WHERE DATE(created_at) = ?",
                (today,)
            ).fetchone()[0]


class ScanDB:
    """Scan history and analytics."""

    @staticmethod
    def record_scan(user_id: str, address: str, chain: str, scan_type: str,
                    risk_score: int, risk_level: str, rarity_tier: str,
                    findings: List[str], is_premium: bool = False):
        with get_db() as db:
            db.execute("""
                INSERT INTO scans (user_id, address, chain, scan_type, risk_score,
                                   risk_level, rarity_tier, findings_json, is_premium)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, address.lower(), chain, scan_type, risk_score,
                  risk_level, rarity_tier, json.dumps(findings), int(is_premium)))

            # Update user totals
            db.execute(f"""
                UPDATE users SET
                    scans_total = scans_total + 1,
                    scans_{scan_type} = scans_{scan_type} + 1,
                    last_seen = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))

    @staticmethod
    def get_user_scans(user_id: str, limit: int = 10) -> List[Dict]:
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM scans WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_stats() -> Dict:
        with get_db() as db:
            total_scans = db.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
            today = datetime.utcnow().strftime("%Y-%m-%d")
            scans_today = db.execute(
                "SELECT COUNT(*) FROM scans WHERE DATE(created_at) = ?", (today,)
            ).fetchone()[0]
            avg_score = db.execute("SELECT AVG(risk_score) FROM scans").fetchone()[0] or 0
            high_risk = db.execute(
                "SELECT COUNT(*) FROM scans WHERE risk_score >= 80"
            ).fetchone()[0]
            return {
                "total_scans": total_scans,
                "scans_today": scans_today,
                "avg_risk_score": round(avg_score, 1),
                "high_risk_detected": high_risk,
            }


class CollectionDB:
    """Card collection tracking."""

    @staticmethod
    def add_or_update(user_id: str, address: str, chain: str, rarity_tier: str):
        with get_db() as db:
            db.execute("""
                INSERT INTO collection (user_id, address, chain, rarity_tier)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, address) DO UPDATE SET
                    scan_count = scan_count + 1,
                    rarity_tier = excluded.rarity_tier
            """, (user_id, address.lower(), chain, rarity_tier))
            count = db.execute(
                "SELECT COUNT(*) FROM collection WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            db.execute("UPDATE users SET collection_size = ? WHERE user_id = ?", (count, user_id))

    @staticmethod
    def get_collection(user_id: str, limit: int = 25) -> List[Dict]:
        with get_db() as db:
            rows = db.execute("""
                SELECT * FROM collection WHERE user_id = ?
                ORDER BY first_scanned_at DESC LIMIT ?
            """, (user_id, limit)).fetchall()
            return [dict(r) for r in rows]


class DailyUsageDB:
    """Free tier enforcement."""

    @staticmethod
    def get_usage(user_id: str, date: str = None) -> Dict:
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM daily_usage WHERE user_id = ? AND date = ?",
                (user_id, date)
            ).fetchone()
            if row:
                return {"contract": row["contract_scans"], "wallet": row["wallet_scans"]}
            return {"contract": 0, "wallet": 0}

    @staticmethod
    def increment(user_id: str, scan_type: str, limit: int = 3) -> Tuple[bool, Dict]:
        date = datetime.utcnow().strftime("%Y-%m-%d")
        with get_db() as db:
            db.execute("""
                INSERT INTO daily_usage (user_id, date, contract_scans, wallet_scans)
                VALUES (?, ?, 0, 0)
                ON CONFLICT(user_id, date) DO NOTHING
            """, (user_id, date))

            col = "contract_scans" if scan_type == "contract" else "wallet_scans"
            used = db.execute(
                f"SELECT {col} FROM daily_usage WHERE user_id = ? AND date = ?",
                (user_id, date)
            ).fetchone()[0]

            if used >= limit:
                return False, {"used": used, "limit": limit, "remaining": 0, "tier": "free"}

            db.execute(
                f"UPDATE daily_usage SET {col} = {col} + 1 WHERE user_id = ? AND date = ?",
                (user_id, date)
            )
            return True, {"used": used + 1, "limit": limit, "remaining": limit - used - 1, "tier": "free"}


class AchievementDB:
    """Achievement tracking."""

    @staticmethod
    def unlock(user_id: str, achievement_key: str) -> bool:
        """Returns True if newly unlocked, False if already had."""
        with get_db() as db:
            try:
                db.execute("""
                    INSERT INTO achievements (user_id, achievement_key)
                    VALUES (?, ?)
                """, (user_id, achievement_key))
                count = db.execute(
                    "SELECT COUNT(*) FROM achievements WHERE user_id = ?", (user_id,)
                ).fetchone()[0]
                db.execute(
                    "UPDATE users SET achievements_count = ? WHERE user_id = ?",
                    (count, user_id)
                )
                return True
            except sqlite3.IntegrityError:
                return False

    @staticmethod
    def get_unlocked(user_id: str) -> List[str]:
        with get_db() as db:
            rows = db.execute(
                "SELECT achievement_key FROM achievements WHERE user_id = ?",
                (user_id,)
            ).fetchall()
            return [r[0] for r in rows]


class SocialPointsDB:
    """SocialFi points and referral tracking."""

    @staticmethod
    def ensure_user(user_id: str):
        with get_db() as db:
            db.execute("""
                INSERT OR IGNORE INTO social_points (user_id)
                VALUES (?)
            """, (user_id,))

    @staticmethod
    def add_points(user_id: str, category: str, amount: int):
        """Add points to a category. category: referral, scan, share, challenge"""
        SocialPointsDB.ensure_user(user_id)
        with get_db() as db:
            db.execute(f"""
                UPDATE social_points SET
                    {category}_points = {category}_points + ?,
                    total_points = total_points + ?,
                    lifetime_points = lifetime_points + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (amount, amount, amount, user_id))

    @staticmethod
    def get_points(user_id: str) -> Dict:
        SocialPointsDB.ensure_user(user_id)
        with get_db() as db:
            row = db.execute("SELECT * FROM social_points WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else {
                "total_points": 0, "referral_points": 0, "scan_points": 0,
                "share_points": 0, "challenge_points": 0, "lifetime_points": 0
            }

    @staticmethod
    def get_leaderboard(limit: int = 20) -> List[Dict]:
        with get_db() as db:
            rows = db.execute("""
                SELECT sp.*, u.first_name, u.username
                FROM social_points sp
                JOIN users u ON sp.user_id = u.user_id
                ORDER BY sp.total_points DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]


class ReferralDB:
    """Referral tracking."""

    @staticmethod
    def create_referral(referrer_id: str, referred_id: str) -> bool:
        """Returns True if new referral created."""
        with get_db() as db:
            try:
                db.execute("""
                    INSERT INTO referrals (referrer_id, referred_id, status)
                    VALUES (?, ?, 'pending')
                """, (referrer_id, referred_id))
                return True
            except sqlite3.IntegrityError:
                return False

    @staticmethod
    def complete_referral(referred_id: str) -> Optional[str]:
        """Mark referral as complete when referred user scans. Returns referrer_id."""
        with get_db() as db:
            row = db.execute(
                "SELECT referrer_id FROM referrals WHERE referred_id = ? AND status = 'pending'",
                (referred_id,)
            ).fetchone()
            if row:
                referrer_id = row["referrer_id"]
                db.execute(
                    "UPDATE referrals SET status = 'complete', points_awarded = 100 WHERE referred_id = ?",
                    (referred_id,)
                )
                SocialPointsDB.add_points(referrer_id, "referral", 100)
                return referrer_id
            return None

    @staticmethod
    def get_referrals(referrer_id: str) -> Dict:
        with get_db() as db:
            total = db.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (referrer_id,)
            ).fetchone()[0]
            complete = db.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND status = 'complete'", (referrer_id,)
            ).fetchone()[0]
            points = db.execute(
                "SELECT SUM(points_awarded) FROM referrals WHERE referrer_id = ?", (referrer_id,)
            ).fetchone()[0] or 0
            return {"total": total, "complete": complete, "points": points}


class ChallengeDB:
    """Community challenges."""

    @staticmethod
    def ensure_defaults():
        defaults = [
            ("first_scan", "First Blood", "Perform your first scan", 50, None),
            ("rug_spotter", "Rug Spotter", "Find a MYTHIC risk token", 200, None),
            ("daily_grind", "Daily Grind", "Scan 5 contracts in one day", 100, None),
            ("social_share", "Social Shiller", "Share a scan result", 75, None),
            ("invite_5", "Recruiter", "Invite 5 friends who scan", 500, None),
        ]
        with get_db() as db:
            for key, name, desc, points, expires in defaults:
                db.execute("""
                    INSERT OR IGNORE INTO challenges (key, name, description, points, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (key, name, desc, points, expires))

    @staticmethod
    def get_active() -> List[Dict]:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM challenges WHERE active = 1 ORDER BY points DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def complete_challenge(user_id: str, challenge_key: str) -> Optional[int]:
        """Returns points awarded if newly completed, None if already done."""
        with get_db() as db:
            challenge = db.execute(
                "SELECT * FROM challenges WHERE key = ? AND active = 1", (challenge_key,)
            ).fetchone()
            if not challenge:
                return None
            try:
                db.execute("""
                    INSERT INTO user_challenges (user_id, challenge_key)
                    VALUES (?, ?)
                """, (user_id, challenge_key))
                SocialPointsDB.add_points(user_id, "challenge", challenge["points"])
                return challenge["points"]
            except sqlite3.IntegrityError:
                return None

    @staticmethod
    def get_user_completed(user_id: str) -> List[Dict]:
        with get_db() as db:
            rows = db.execute("""
                SELECT uc.*, c.name, c.description, c.points
                FROM user_challenges uc
                JOIN challenges c ON uc.challenge_key = c.key
                WHERE uc.user_id = ?
                ORDER BY uc.completed_at DESC
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]


class ShareDB:
    """Track shared scans for points."""

    @staticmethod
    def record_share(user_id: str, address: str, platform: str) -> int:
        with get_db() as db:
            # Max 10 shares per day per platform
            today = datetime.utcnow().strftime("%Y-%m-%d")
            count = db.execute("""
                SELECT COUNT(*) FROM shared_scans
                WHERE user_id = ? AND platform = ? AND DATE(created_at) = ?
            """, (user_id, platform, today)).fetchone()[0]
            if count >= 10:
                return 0
            points = 25
            db.execute("""
                INSERT INTO shared_scans (user_id, address, platform, points)
                VALUES (?, ?, ?, ?)
            """, (user_id, address, platform, points))
            SocialPointsDB.add_points(user_id, "share", points)
            return points


class AdminLogDB:
    """Admin action audit trail."""

    @staticmethod
    def log(admin_id: str, action: str, target_id: str = None, details: str = None):
        with get_db() as db:
            db.execute("""
                INSERT INTO admin_logs (admin_id, action, target_id, details)
                VALUES (?, ?, ?, ?)
            """, (admin_id, action, target_id, details))


# Initialize on import
init_db()
ChallengeDB.ensure_defaults()
