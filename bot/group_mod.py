"""
Rug Muncher — Group Auto-Moderation
====================================
Protects groups from scam links, spam, and malicious contracts.

Actions:
  • Delete messages with known scam contracts
  • Delete messages with honeypot addresses
  • Warn users posting suspicious links
  • Auto-ban repeat offenders
  • Pin safety reminders
"""

import re
import logging
from typing import Optional, List
from dataclasses import dataclass

logger = logging.getLogger("group_mod")

# Known scam patterns
SCAM_PATTERNS = [
    re.compile(r"t\.me/\+?[a-zA-Z0-9_]+.*(free|airdrop|claim|gift)", re.I),
    re.compile(r"(claim|airdrop|free)\s+(nft|token|reward)", re.I),
    re.compile(r"connect\s+(wallet|metamask|trust)", re.I),
    re.compile(r"verify\s+(wallet|account)\s+now", re.I),
]

# Known bad domains
BAD_DOMAINS = [
    "connect-wallet.vercel.app",
    "verify-eth.com",
    "claim-airdrop.xyz",
    "free-nfts.io",
    "wallet-connect.digital",
]

SUSPICIOUS_TLD = [".tk", ".ml", ".ga", ".cf", ".gq"]


@dataclass
class ModAction:
    action: str       # delete, warn, ban, none
    reason: str
    severity: int     # 1-10


class GroupModerator:
    """Scan group messages for scams and take action."""

    WARN_THRESHOLD = 2    # Warnings before considering ban
    BAN_THRESHOLD = 3     # Warnings before auto-ban

    def __init__(self):
        self.user_warnings: dict = {}

    def check_message(self, text: str, user_id: str) -> ModAction:
        """Check a message and return recommended action."""
        text_lower = text.lower()

        # Check for scam patterns
        for pattern in SCAM_PATTERNS:
            if pattern.search(text):
                return ModAction("delete", "Scam pattern detected", 8)

        # Check for bad domains
        for domain in BAD_DOMAINS:
            if domain in text_lower:
                return ModAction("delete", f"Known phishing domain: {domain}", 9)

        # Check suspicious TLDs in URLs
        for tld in SUSPICIOUS_TLD:
            if tld in text_lower and "http" in text_lower:
                return ModAction("warn", f"Suspicious link detected ({tld})", 5)

        # Check for raw contract addresses that might be scams
        # (In a real bot, you'd check against a DB of known scams)
        evm_match = re.search(r"0x[a-fA-F0-9]{40}", text)
        if evm_match and any(kw in text_lower for kw in ["free", "claim", "airdrop", "send", "bonus"]):
            return ModAction("warn", "Unverified contract in promo message", 6)

        return ModAction("none", "", 0)

    def record_warning(self, user_id: str) -> int:
        """Record a warning and return current count."""
        self.user_warnings[user_id] = self.user_warnings.get(user_id, 0) + 1
        return self.user_warnings[user_id]

    def get_warnings(self, user_id: str) -> int:
        return self.user_warnings.get(user_id, 0)

    def reset_warnings(self, user_id: str):
        self.user_warnings[user_id] = 0

    def format_warn_message(self, user_name: str, reason: str, count: int) -> str:
        return (
            f"<b>⚠️ WARNING</b>\n\n"
            f"{user_name}, your message was flagged.\n"
            f"<i>Reason: {reason}</i>\n\n"
            f"Strike: <b>{count}/{self.BAN_THRESHOLD}</b>\n"
            f"Repeated violations will result in removal.\n\n"
            f"<i>Stay safe — verify contracts with @rugmuncherbot</i>"
        )


# Singleton
group_moderator = GroupModerator()
