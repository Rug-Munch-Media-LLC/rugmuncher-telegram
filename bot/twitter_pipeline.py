"""
Twitter/X Intelligence Pipeline
Monitors 71 high-signal crypto accounts, catches tweets early,
rewrites/improves content, and posts to RMI channels.

Priority routing:
- CRITICAL: Immediate post to relevant channels
- HIGH: Post within 5 minutes
- MEDIUM: Post within 30 minutes
"""
import os
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import requests

logger = logging.getLogger("twitter_pipeline")

# ── Configuration ──
TWITTER_ACCOUNTS_FILE = "/root/ecosystems/rugmuncher/bot/bot/twitter_accounts.json"
SEEN_TWEETS_FILE = "/root/ecosystems/rugmuncher/bot/bot/seen_tweets.json"
MAX_TWEETS_PER_CYCLE = 50
MIN_ENGAGEMENT = 50  # Minimum likes to consider

@dataclass
class Tweet:
    """A tweet to be processed."""
    handle: str
    name: str
    category: str
    text: str
    tweet_id: str
    engagement: int  # likes + retweets
    timestamp: str
    url: str
    priority: str = "MEDIUM"
    
    @property
    def content_hash(self) -> str:
        """Generate hash for dedup."""
        text = f"{self.handle}|{self.text[:100]}"
        return hashlib.md5(text.encode()).hexdigest()[:16]

class TwitterMonitor:
    """Monitor Twitter accounts for high-signal content."""
    
    def __init__(self):
        self.accounts = self._load_accounts()
        self.seen_tweets = self._load_seen_tweets()
        self.recent_posts: Dict[str, datetime] = {}
        
    def _load_accounts(self) -> Dict:
        """Load Twitter accounts from JSON file."""
        try:
            with open(TWITTER_ACCOUNTS_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load Twitter accounts: {e}")
            return {}
    
    def _load_seen_tweets(self) -> Set[str]:
        """Load set of seen tweet IDs."""
        try:
            with open(SEEN_TWEETS_FILE) as f:
                data = json.load(f)
                return set(data.get("seen", []))
        except:
            return set()
    
    def _save_seen_tweets(self):
        """Save seen tweet IDs."""
        try:
            with open(SEEN_TWEETS_FILE, "w") as f:
                json.dump({"seen": list(self.seen_tweets), "updated": datetime.utcnow().isoformat()}, f)
        except Exception as e:
            logger.error(f"Failed to save seen tweets: {e}")
    
    def fetch_tweets(self) -> List[Tweet]:
        """Fetch tweets from all monitored accounts with full fallback chain."""
        tweets = []
        
        # Use the fallback system for robust fetching
        from bot.fallback_system import twitter_monitor as fallback_monitor
        
        for category_name, category_data in self.accounts.items():
            for account in category_data["accounts"]:
                handle = account["handle"]
                
                # Skip if we've seen recent tweets from this account
                if handle in self.recent_posts:
                    if (datetime.utcnow() - self.recent_posts[handle]).total_seconds() < 300:
                        continue
                
                # Try fallback system first (API v2 → Nitter → RSS-Bridge → TG → Web → Third-party)
                try:
                    fallback_tweets = fallback_monitor.fetch_tweet_fallbacks(handle, 3)
                    for ft in fallback_tweets:
                        tweet_id = ft.get("url", "").split("/")[-1]
                        if not tweet_id or tweet_id in self.seen_tweets:
                            continue
                        
                        tweets.append(Tweet(
                            handle=handle,
                            name=account["name"],
                            category=category_name,
                            text=ft.get("text", ""),
                            tweet_id=tweet_id,
                            engagement=ft.get("engagement", 0),
                            timestamp=ft.get("date", ""),
                            url=ft.get("url", ""),
                            priority=category_data["priority"]
                        ))
                        self.seen_tweets.add(tweet_id)
                        self.recent_posts[handle] = datetime.utcnow()
                except Exception as e:
                    logger.error(f"Fallback fetch failed for @{handle}: {e}")
        
        # Sort by engagement (highest first)
        tweets.sort(key=lambda t: t.engagement, reverse=True)
        return tweets[:MAX_TWEETS_PER_CYCLE]
    
    def rewrite_tweet(self, tweet: Tweet) -> str:
        """Rewrite tweet content to be more engaging and RMI-branded.
        
        Rules:
        - Keep core information intact
        - Add RMI branding/context
        - Improve readability
        - Add relevant emojis
        - Include call-to-action
        """
        text = tweet.text
        
        # Remove URLs from original
        import re
        text = re.sub(r'https?://\S+', '', text).strip()
        text = re.sub(r'@\w+', '', text).strip()
        
        # Category-specific rewriting
        category_rewrites = {
            "whale_trackers": {
                "prefix": "🐋 WHALE ALERT",
                "format": "Large transaction detected",
                "suffix": "🤖 Verify this contract: https://t.me/rugmunchbot"
            },
            "breaking_news": {
                "prefix": "🚨 BREAKING",
                "format": "Major development",
                "suffix": "📰 Source: @{handle}"
            },
            "alpha_hunters": {
                "prefix": "💎 ALPHA SIGNAL",
                "format": "High-conviction call",
                "suffix": "🔍 Deep scan: https://t.me/rugmunchbot"
            },
            "technical_analysts": {
                "prefix": "📊 MARKET ANALYSIS",
                "format": "Technical insight",
                "suffix": "📈 Full analysis: https://t.me/rugmunchbot"
            },
            "narrative_scouts": {
                "prefix": "🎯 NARRATIVE ALERT",
                "format": "Emerging trend",
                "suffix": "🔬 Research: https://t.me/rugmunchbot"
            },
            "security_watchers": {
                "prefix": "⚠️ SECURITY ALERT",
                "format": "Security issue",
                "suffix": "🛡️ Verify safety: https://t.me/rugmunchbot"
            },
            "meme_degen": {
                "prefix": "🚀 DEGEN ALERT",
                "format": "Meme coin activity",
                "suffix": "🔍 Scan contract: https://t.me/rugmunchbot"
            },
            "dev_builders": {
                "prefix": "🔧 BUILDER UPDATE",
                "format": "Development news",
                "suffix": "📊 Track progress: https://t.me/rugmunchbot"
            }
        }
        
        rewrite = category_rewrites.get(tweet.category, {
            "prefix": "📌 UPDATE",
            "format": "New information",
            "suffix": "🔗 Source: @{handle}"
        })
        
        # Build formatted content
        formatted = (
            f"<b>{rewrite['prefix']}</b>\n\n"
            f"{text}\n\n"
            f"<i>{rewrite['suffix'].format(handle=tweet.handle)}</i>\n"
            f"<i>Engagement: {tweet.engagement:,} | {tweet.timestamp}</i>"
        )
        
        return formatted
    
    def route_to_channels(self, tweet: Tweet) -> List[str]:
        """Determine which channels should receive this tweet."""
        category_data = self.accounts.get(tweet.category, {})
        return category_data.get("post_to", [])
    
    async def process_and_post(self, bot) -> int:
        """Fetch, rewrite, and post tweets. Returns count of posted tweets."""
        tweets = self.fetch_tweets()
        if not tweets:
            return 0
        
        posted = 0
        for tweet in tweets:
            # Check rate limits
            channels = self.route_to_channels(tweet)
            for channel in channels:
                # Check if we've posted recently to this channel
                channel_key = f"channel_{channel}"
                if channel_key in self.recent_posts:
                    if (datetime.utcnow() - self.recent_posts[channel_key]).total_seconds() < 600:
                        continue
                
                # Rewrite and post
                formatted = self.rewrite_tweet(tweet)
                chat_id = CHANNEL_IDS.get(channel, "")
                
                if chat_id and bot:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=formatted,
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                        self.recent_posts[channel_key] = datetime.utcnow()
                        posted += 1
                        logger.info(f"Posted tweet from @{tweet.handle} to {channel}")
                    except Exception as e:
                        logger.error(f"Failed to post tweet: {e}")
        
        self._save_seen_tweets()
        return posted

# ── Channel ID mapping ──
CHANNEL_IDS = {
    "main_channel": os.getenv("CHANNEL_CRYPTO_RUGMUNCHER", ""),
    "rmi_news": os.getenv("CHANNEL_RMI_NEWS", ""),
    "crypto_alerts": os.getenv("CHANNEL_CRYPTO_ALERTS", ""),
    "crypto_alpha": os.getenv("CHANNEL_CRYPTO_ALPHA", ""),
    "rmiscans": os.getenv("CHANNEL_COMMUNITY_SCANS", ""),
    "rmi_updates": os.getenv("CHANNEL_RMI_UPDATES", ""),
}

# ── Main instance ──
twitter_monitor = TwitterMonitor()
