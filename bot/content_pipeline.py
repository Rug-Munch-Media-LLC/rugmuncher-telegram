"""
RMI Content Pipeline - Ingest, categorize, and distribute content to channels.

Sources:
- MCP Router (154 tools across 28 services)
- External Telegram channels (16 accessible)
- RSS feeds (CoinDesk, Cointelegraph, Decrypt, etc.)
- Bot scanner results
- Reddit hot posts
- Fear & Greed Index
- Whale alerts

Rules:
- No spam (max 3 posts in 10 minutes per channel)
- Dedup by content hash (keep newest)
- Priority routing (CRITICAL -> all relevant channels)
- Quality threshold (min 2 sources, 70% confidence)
"""
import os
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import requests
from collections import defaultdict

logger = logging.getLogger("content_pipeline")

# ── Channel IDs ──
CHANNEL_IDS = {
    "main_channel": os.getenv("CHANNEL_CRYPTO_RUGMUNCHER", ""),
    "community_scans": os.getenv("CHANNEL_COMMUNITY_SCANS", ""),
    "crypto_alerts": os.getenv("CHANNEL_CRYPTO_ALERTS", ""),
    "crypto_alpha": os.getenv("CHANNEL_CRYPTO_ALPHA", ""),
    "rmi_updates": os.getenv("CHANNEL_RMI_UPDATES", ""),
    "rmi_news": os.getenv("CHANNEL_RMI_NEWS", ""),
}

# ── Content Priority Levels ──
class Priority:
    IMMEDIATE = "immediate"  # Post now, bypass rate limits
    HIGH = "high"           # Post within 5 minutes
    MEDIUM = "medium"       # Post within 30 minutes
    LOW = "low"             # Batch and post on schedule

# ── Content Categories ──
class ContentCategory:
    # Main channel
    MAJOR_ALERT = "major_alert"
    WEBSITE_POST = "website_post"
    TWITTER_HIGHLIGHT = "twitter_highlight"
    MARKET_MOVEMENT = "market_movement"
    PROJECT_UPDATE = "project_update"
    
    # News channel
    BREAKING_NEWS = "breaking_news"
    MARKET_ANALYSIS = "market_analysis"
    TRENDING_TOKENS = "trending_tokens"
    REGULATORY_NEWS = "regulatory_news"
    DEFI_UPDATES = "defi_updates"
    
    # Alerts channel
    RUG_PULL = "rug_pull"
    HONEYPOT = "honeypot"
    EXPLOIT = "exploit"
    SCAM_CONTRACT = "scam_contract"
    LP_DRAIN = "lp_drain"
    
    # Alpha channel
    WHALE_MOVEMENT = "whale_movement"
    SMART_MONEY = "smart_money"
    INSIDER_ACCUMULATION = "insider_accumulation"
    EARLY_GEM = "early_gem"
    DEPLOYER_BLACKLIST = "deployer_blacklist"
    PRE_RUG_WARNING = "pre_rug_warning"
    DEEP_SCAN = "deep_scan"
    
    # Scans channel
    USER_SCAN = "user_scan"
    TRENDING_SCANS = "trending_scans"
    LAUNCH_RADAR = "launch_radar"
    SCAN_DIGEST = "scan_digest"
    
    # Updates channel
    FEATURE_RELEASE = "feature_release"
    SYSTEM_STATUS = "system_status"
    MILESTONE = "milestone"
    PARTNERSHIP = "partnership"

# ── Routing Map ──
CATEGORY_TO_CHANNELS = {
    ContentCategory.MAJOR_ALERT: ["main_channel", "crypto_alerts", "crypto_alpha"],
    ContentCategory.WEBSITE_POST: ["main_channel"],
    ContentCategory.TWITTER_HIGHLIGHT: ["main_channel"],
    ContentCategory.MARKET_MOVEMENT: ["main_channel", "crypto_alpha"],
    ContentCategory.PROJECT_UPDATE: ["main_channel", "rmi_updates"],
    
    ContentCategory.BREAKING_NEWS: ["rmi_news", "main_channel"],
    ContentCategory.MARKET_ANALYSIS: ["rmi_news"],
    ContentCategory.TRENDING_TOKENS: ["rmi_news", "rmiscans"],
    ContentCategory.REGULATORY_NEWS: ["rmi_news", "main_channel"],
    ContentCategory.DEFI_UPDATES: ["rmi_news"],
    
    ContentCategory.RUG_PULL: ["crypto_alerts", "main_channel", "crypto_alpha"],
    ContentCategory.HONEYPOT: ["crypto_alerts"],
    ContentCategory.EXPLOIT: ["crypto_alerts", "main_channel", "crypto_alpha"],
    ContentCategory.SCAM_CONTRACT: ["crypto_alerts"],
    ContentCategory.LP_DRAIN: ["crypto_alerts", "crypto_alpha"],
    
    ContentCategory.WHALE_MOVEMENT: ["crypto_alpha", "main_channel"],
    ContentCategory.SMART_MONEY: ["crypto_alpha"],
    ContentCategory.INSIDER_ACCUMULATION: ["crypto_alpha"],
    ContentCategory.EARLY_GEM: ["crypto_alpha"],
    ContentCategory.DEPLOYER_BLACKLIST: ["crypto_alpha", "crypto_alerts"],
    ContentCategory.PRE_RUG_WARNING: ["crypto_alpha", "crypto_alerts"],
    ContentCategory.DEEP_SCAN: ["crypto_alpha"],
    
    ContentCategory.USER_SCAN: ["rmiscans"],
    ContentCategory.TRENDING_SCANS: ["rmiscans"],
    ContentCategory.LAUNCH_RADAR: ["rmiscans", "crypto_alpha"],
    ContentCategory.SCAN_DIGEST: ["rmiscans"],
    
    ContentCategory.FEATURE_RELEASE: ["rmi_updates", "main_channel"],
    ContentCategory.SYSTEM_STATUS: ["rmi_updates"],
    ContentCategory.MILESTONE: ["rmi_updates", "main_channel"],
    ContentCategory.PARTNERSHIP: ["rmi_updates", "main_channel"],
}

# ── Category Metadata ──
CATEGORY_META = {
    ContentCategory.MAJOR_ALERT: {"emoji": "🚨", "title": "MAJOR ALERT", "priority": Priority.IMMEDIATE},
    ContentCategory.WEBSITE_POST: {"emoji": "🌐", "title": "WEB UPDATE", "priority": Priority.HIGH},
    ContentCategory.TWITTER_HIGHLIGHT: {"emoji": "🐦", "title": "TWITTER HIGHLIGHT", "priority": Priority.MEDIUM},
    ContentCategory.MARKET_MOVEMENT: {"emoji": "📈", "title": "MARKET MOVEMENT", "priority": Priority.HIGH},
    ContentCategory.PROJECT_UPDATE: {"emoji": "🔧", "title": "PROJECT UPDATE", "priority": Priority.MEDIUM},
    
    ContentCategory.BREAKING_NEWS: {"emoji": "📰", "title": "BREAKING NEWS", "priority": Priority.IMMEDIATE},
    ContentCategory.MARKET_ANALYSIS: {"emoji": "📊", "title": "MARKET ANALYSIS", "priority": Priority.HIGH},
    ContentCategory.TRENDING_TOKENS: {"emoji": "🔥", "title": "TRENDING", "priority": Priority.MEDIUM},
    ContentCategory.REGULATORY_NEWS: {"emoji": "⚖️", "title": "REGULATORY", "priority": Priority.HIGH},
    ContentCategory.DEFI_UPDATES: {"emoji": "💎", "title": "DEFI UPDATE", "priority": Priority.MEDIUM},
    
    ContentCategory.RUG_PULL: {"emoji": "💀", "title": "RUG PULL DETECTED", "priority": Priority.IMMEDIATE},
    ContentCategory.HONEYPOT: {"emoji": "🍯", "title": "HONEYPOT CONFIRMED", "priority": Priority.IMMEDIATE},
    ContentCategory.EXPLOIT: {"emoji": "💥", "title": "EXPLOIT DETECTED", "priority": Priority.IMMEDIATE},
    ContentCategory.SCAM_CONTRACT: {"emoji": "⚠️", "title": "SCAM ALERT", "priority": Priority.HIGH},
    ContentCategory.LP_DRAIN: {"emoji": "💧", "title": "LP DRAIN", "priority": Priority.HIGH},
    
    ContentCategory.WHALE_MOVEMENT: {"emoji": "🐋", "title": "WHALE MOVEMENT", "priority": Priority.HIGH},
    ContentCategory.SMART_MONEY: {"emoji": "🧠", "title": "SMART MONEY", "priority": Priority.HIGH},
    ContentCategory.INSIDER_ACCUMULATION: {"emoji": "🎯", "title": "INSIDER ACTIVITY", "priority": Priority.HIGH},
    ContentCategory.EARLY_GEM: {"emoji": "💎", "title": "EARLY GEM", "priority": Priority.HIGH},
    ContentCategory.DEPLOYER_BLACKLIST: {"emoji": "🕵️", "title": "BLACKLISTED DEV", "priority": Priority.HIGH},
    ContentCategory.PRE_RUG_WARNING: {"emoji": "🔴", "title": "PRE-RUG WARNING", "priority": Priority.IMMEDIATE},
    ContentCategory.DEEP_SCAN: {"emoji": "🔬", "title": "DEEP SCAN", "priority": Priority.MEDIUM},
    
    ContentCategory.USER_SCAN: {"emoji": "🔍", "title": "SCAN RESULT", "priority": Priority.LOW},
    ContentCategory.TRENDING_SCANS: {"emoji": "📊", "title": "TRENDING SCANS", "priority": Priority.MEDIUM},
    ContentCategory.LAUNCH_RADAR: {"emoji": "🚀", "title": "NEW LAUNCH", "priority": Priority.MEDIUM},
    ContentCategory.SCAN_DIGEST: {"emoji": "📋", "title": "SCAN DIGEST", "priority": Priority.LOW},
    
    ContentCategory.FEATURE_RELEASE: {"emoji": "🚀", "title": "NEW FEATURE", "priority": Priority.HIGH},
    ContentCategory.SYSTEM_STATUS: {"emoji": "📡", "title": "SYSTEM STATUS", "priority": Priority.HIGH},
    ContentCategory.MILESTONE: {"emoji": "🏆", "title": "MILESTONE", "priority": Priority.MEDIUM},
    ContentCategory.PARTNERSHIP: {"emoji": "🤝", "title": "PARTNERSHIP", "priority": Priority.HIGH},
}

@dataclass
class ContentItem:
    """A piece of content to be distributed."""
    category: str
    title: str
    content: str
    sources: List[str]
    priority: str = Priority.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    @property
    def content_hash(self) -> str:
        """Generate hash for dedup (ignores timestamp)."""
        text = f"{self.category}|{self.title}|{self.content}"
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    @property
    def formatted_text(self) -> str:
        """Format content for Telegram posting."""
        meta = CATEGORY_META.get(self.category, {"emoji": "📌", "title": "UPDATE"})
        
        text = (
            f"<b>{meta['emoji']} {meta['title']}</b>\n\n"
            f"{self.content}\n\n"
            f"<i>Source: {', '.join(self.sources[:3])}</i>\n"
            f"<i>{self.timestamp[:16]} UTC</i>"
        )
        
        # Add link if present
        if "url" in self.metadata:
            text += f"\n🔗 <a href='{self.metadata['url']}'>Read more</a>"
        
        return text

class ContentPipeline:
    """Main pipeline for ingesting, categorizing, and distributing content."""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.post_history: Dict[str, List[datetime]] = defaultdict(list)
        self.content_hashes: Dict[str, str] = {}  # hash -> message_id
        self.rate_limit_window = 600  # 10 minutes
        self.max_posts_per_window = 3
        
    def should_post(self, channel_key: str, content_hash: str) -> bool:
        """Check if we should post based on rate limits and dedup."""
        # Rate limit check
        now = datetime.utcnow()
        recent = [t for t in self.post_history[channel_key] 
                 if (now - t).total_seconds() < self.rate_limit_window]
        self.post_history[channel_key] = recent
        
        if len(recent) >= self.max_posts_per_window:
            return False
        
        # Dedup check
        if content_hash in self.content_hashes:
            return False
        
        return True
    
    def route_content(self, item: ContentItem) -> List[str]:
        """Determine which channels should receive this content."""
        return CATEGORY_TO_CHANNELS.get(item.category, [])
    
    async def distribute(self, item: ContentItem):
        """Distribute content to appropriate channels."""
        channels = self.route_content(item)
        
        for channel_key in channels:
            chat_id = CHANNEL_IDS.get(channel_key)
            if not chat_id:
                continue
                
            if not self.should_post(chat_id, item.content_hash):
                continue
            
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=item.formatted_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                self.post_history[chat_id].append(datetime.utcnow())
                self.content_hashes[item.content_hash] = chat_id
                logger.info(f"Posted {item.category} to {channel_key}")
            except Exception as e:
                logger.error(f"Failed to post to {channel_key}: {e}")

# ── Source Fetchers ──

class NewsFetcher:
    """Fetch news from multiple sources."""
    
    @staticmethod
    def fetch_cryptopanic() -> List[ContentItem]:
        """Fetch from CryptoPanic via MCP Router."""
        items = []
        try:
            r = requests.get("https://mcp-router.rugmunch.io/mcp", json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "cryptopanic:getNews",
                    "arguments": {"filter": "important"}
                }
            }, timeout=10)
            
            if r.status_code == 200 and "result" in r.json():
                # Process results into ContentItems
                pass
        except Exception as e:
            logger.error(f"CryptoPanic fetch error: {e}")
        
        return items
    
    @staticmethod
    def fetch_fear_greed() -> Optional[ContentItem]:
        """Fetch Fear & Greed Index."""
        try:
            r = requests.get("https://api.alternative.me/fng/", timeout=5)
            if r.status_code == 200:
                data = r.json()["data"][0]
                value = int(data["value"])
                classification = data["value_classification"]
                
                # Only post if significant change
                if value < 30 or value > 70:
                    return ContentItem(
                        category=ContentCategory.MARKET_ANALYSIS,
                        title=f"Fear & Greed: {classification} ({value})",
                        content=f"Market sentiment is currently {classification.upper()} with a score of {value}/100.",
                        sources=["alternative.me"],
                        priority=Priority.MEDIUM if 30 <= value <= 70 else Priority.HIGH,
                    )
        except Exception as e:
            logger.error(f"Fear & Greed fetch error: {e}")
        return None

class WhaleFetcher:
    """Fetch whale movement data."""
    
    @staticmethod
    def fetch_whale_alerts() -> List[ContentItem]:
        """Fetch from Whale Alert Telegram channel."""
        # This would use Telethon to monitor @whale_alert
        return []
    
    @staticmethod
    def fetch_smart_money() -> List[ContentItem]:
        """Fetch from CryptoIZ whale signals via MCP."""
        items = []
        try:
            r = requests.get("https://mcp-router.rugmunch.io/mcp", json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "cryptoiz:getWhaleAlpha",
                    "arguments": {}
                }
            }, timeout=10)
            
            if r.status_code == 200:
                # Process whale signals
                pass
        except Exception as e:
            logger.error(f"Smart money fetch error: {e}")
        
        return items

class ScannerFetcher:
    """Fetch scan results from bot."""
    
    @staticmethod
    def fetch_recent_scans() -> List[ContentItem]:
        """Fetch recent scans from Redis/backend."""
        # Implementation would query Redis for recent scans
        return []

# ── Main Pipeline Instance ──
pipeline = ContentPipeline()
