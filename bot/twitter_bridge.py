"""
Rug Muncher — Twitter/X Auto-Post Bridge
=========================================
Auto-posts high-value findings to Twitter/X.

Triggers:
  • MYTHIC risk (81-100) → IMMEDIATE tweet
  • LEGENDARY risk (61-80) → Tweet with delay check
  • Daily top rug → End of day summary tweet
  • Safe gem with 90+ score → Alpha tweet
"""

import os
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger("twitter_bridge")

# Try to import tweepy (optional dependency)
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False


class TwitterBridge:
    """Post alerts to Twitter/X."""

    def __init__(self):
        self.client = None
        self.enabled = False
        self._init_client()

    def _init_client(self):
        if not TWEEPY_AVAILABLE:
            logger.info("tweepy not installed. Twitter bridge disabled.")
            return

        bearer = os.getenv("TWITTER_BEARER_TOKEN", "")
        api_key = os.getenv("TWITTER_API_KEY", "")
        api_secret = os.getenv("TWITTER_API_SECRET", "")
        access_token = os.getenv("TWITTER_ACCESS_TOKEN", "")
        access_secret = os.getenv("TWITTER_ACCESS_SECRET", "")

        if not all([api_key, api_secret, access_token, access_secret]):
            logger.info("Twitter credentials not set. Bridge disabled.")
            return

        try:
            self.client = tweepy.Client(
                bearer_token=bearer,
                consumer_key=api_key,
                consumer_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_secret,
            )
            self.enabled = True
            logger.info("✅ Twitter bridge initialized")
        except Exception as e:
            logger.warning(f"Twitter init failed: {e}")

    def format_tweet(self, address: str, chain: str, risk_score: int,
                     risk_level: str, findings: list) -> str:
        """Format a tweet under 280 chars."""
        short = f"{address[:6]}...{address[-4:]}"
        emoji = "💀" if risk_score >= 81 else "🔥" if risk_score >= 61 else "⚠️"

        tweet = (
            f"{emoji} {risk_level.upper()} RISK DETECTED\n\n"
            f"Contract: {short}\n"
            f"Chain: {chain.upper()}\n"
            f"Score: {risk_score}/100\n\n"
        )

        # Add top finding if space
        if findings:
            top = findings[0][:60]
            remaining = 280 - len(tweet) - len(top) - 10
            if remaining > 0:
                tweet += f"⚠️ {top}\n"

        tweet += "\nScan before you ape → @rugmuncherbot"
        return tweet[:280]

    def post(self, address: str, chain: str, risk_score: int,
             risk_level: str, findings: list) -> bool:
        """Post a tweet. Returns True if posted."""
        if not self.enabled or not self.client:
            return False

        # Only tweet high-value alerts
        if risk_score < 60:
            return False

        text = self.format_tweet(address, chain, risk_score, risk_level, findings)

        try:
            self.client.create_tweet(text=text)
            logger.info(f"🐦 Tweet posted: {address[:10]}... ({risk_score}/100)")
            return True
        except Exception as e:
            logger.warning(f"Tweet failed: {e}")
            return False

    def maybe_post(self, address: str, chain: str, risk_score: int,
                   risk_level: str, findings: list) -> bool:
        """Conditionally post based on severity."""
        if risk_score >= 81:
            return self.post(address, chain, risk_score, risk_level, findings)
        elif risk_score >= 61:
            # Legendary — tweet but less urgent
            return self.post(address, chain, risk_score, risk_level, findings)
        return False


# Singleton
twitter_bridge = TwitterBridge()
